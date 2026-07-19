"""Core proxy-testing logic: parsing, request execution, and result validation.

Validation strategy: fetch the target page once directly (no proxy) as the
reference. Every proxy-fetched page is then compared to that reference by
content similarity — not by HTTP status, which anti-bot walls routinely fake
with a 200 + block page. Supports both fast HTTP requests (httpx) and full
headless browser rendering (Playwright).
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

MAX_LOG_ENTRIES = 4000


def parse_proxies(raw_text: str) -> list[str]:
    """Parse a textarea blob into a deduped, normalized list of proxy URLs.

    Accepts one proxy per line, with or without scheme, with or without
    user:pass@ auth. Blank lines and lines starting with '#' are skipped.
    """
    seen = set()
    proxies = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "://" not in line:
            line = f"http://{line}"
        if line not in seen:
            seen.add(line)
            proxies.append(line)
    return proxies


def parse_playwright_proxy(proxy_url: str) -> dict:
    """Extract server, username, and password for Playwright proxy configuration."""
    parsed = urlparse(proxy_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or ""
    port = parsed.port
    server = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"
    config = {"server": server}
    if parsed.username:
        config["username"] = parsed.username
    if parsed.password:
        config["password"] = parsed.password
    return config


def content_similarity(reference: str, body: str) -> float:
    """Similarity ratio in [0, 1] between the reference page and a proxy response.

    quick_ratio() trades a bit of precision for speed — this runs many times
    per job (proxies x repetitions) against potentially large HTML bodies.
    """
    if not reference and not body:
        return 1.0
    if not reference or not body:
        return 0.0
    return SequenceMatcher(None, reference, body).quick_ratio()


def evaluate_response(status_code: int, body: str, reference_body: str,
                       similarity_threshold: float) -> tuple[bool, float, str]:
    """Decide pass/fail from the FULL response body — never a truncated prefix."""
    if not (200 <= status_code < 300):
        return False, 0.0, f"http_{status_code}"
    if not body:
        return False, 0.0, "empty_body"

    similarity = content_similarity(reference_body, body)
    if similarity >= similarity_threshold:
        return True, similarity, "ok"
    return False, similarity, "content_mismatch"


@dataclass
class TestConfig:
    target_url: str
    engine: str = "httpx"  # httpx | playwright
    repetitions: int = 5
    concurrency: int = 5
    delay_ms: int = 500
    timeout_s: float = 15.0
    similarity_threshold: float = 0.9
    verify_ssl: bool = True


@dataclass
class ProxyResult:
    proxy: str
    attempts: list = field(default_factory=list)  # [{ok, latency, status, reason, similarity}]

    @property
    def summary(self):
        n = len(self.attempts)
        passed = sum(1 for a in self.attempts if a["ok"])
        latencies = [a["latency"] for a in self.attempts if a["latency"] is not None]
        similarities = [a["similarity"] for a in self.attempts if a["similarity"] is not None]
        reasons = {}
        for a in self.attempts:
            if not a["ok"]:
                reasons[a["reason"]] = reasons.get(a["reason"], 0) + 1
        return {
            "proxy": self.proxy,
            "total_requests": n,
            "passed": passed,
            "failed": n - passed,
            "success_rate": round(passed / n, 4) if n else 0.0,
            "avg_similarity": round(sum(similarities) / len(similarities), 4) if similarities else None,
            "total_time_s": round(sum(latencies), 3) if latencies else 0.0,
            "avg_latency_s": round(sum(latencies) / len(latencies), 3) if latencies else None,
            "min_latency_s": round(min(latencies), 3) if latencies else None,
            "max_latency_s": round(max(latencies), 3) if latencies else None,
            "failure_reasons": reasons,
        }


async def fetch_reference(cfg: TestConfig) -> str:
    """Download target page directly (httpx, no proxy) for comparison baseline."""
    timeout = httpx.Timeout(cfg.timeout_s)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=cfg.verify_ssl) as client:
        resp = await asyncio.wait_for(client.get(cfg.target_url), timeout=cfg.timeout_s * 2)
        return resp.text


async def fetch_reference_playwright(cfg: TestConfig) -> str:
    """Download target page directly via Playwright headless browser for comparison baseline."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(ignore_https_errors=not cfg.verify_ssl)
            page = await context.new_page()
            await page.goto(cfg.target_url, timeout=int(cfg.timeout_s * 1000), wait_until="load")
            content = await page.content()
            return content
        finally:
            await browser.close()


async def _single_attempt(client: httpx.AsyncClient, target_url: str, cfg: TestConfig,
                           reference_body: str) -> dict:
    start = time.monotonic()
    try:
        resp = await asyncio.wait_for(client.get(target_url), timeout=cfg.timeout_s * 2)
        body = resp.text
        elapsed = time.monotonic() - start
        ok, similarity, reason = evaluate_response(resp.status_code, body, reference_body,
                                                     cfg.similarity_threshold)
        return {"ok": ok, "latency": elapsed, "status": resp.status_code, "reason": reason,
                "similarity": similarity}
    except (httpx.TimeoutException, asyncio.TimeoutError):
        return {"ok": False, "latency": time.monotonic() - start, "status": None,
                "reason": "timeout", "similarity": None}
    except (httpx.ConnectError, httpx.ProxyError):
        return {"ok": False, "latency": time.monotonic() - start, "status": None,
                "reason": "connection_error", "similarity": None}
    except httpx.HTTPError as e:
        return {"ok": False, "latency": time.monotonic() - start, "status": None,
                "reason": f"http_error:{type(e).__name__}", "similarity": None}
    except Exception as e:
        return {"ok": False, "latency": time.monotonic() - start, "status": None,
                "reason": f"error:{str(e)[:120]}", "similarity": None}


async def test_proxy(proxy_url: str, cfg: TestConfig, reference_body: str, log_fn) -> ProxyResult:
    result = ProxyResult(proxy=proxy_url)
    timeout = httpx.Timeout(cfg.timeout_s)
    log_fn(f"[{proxy_url}] starting ({cfg.repetitions}x)")
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout,
                                      follow_redirects=True, verify=cfg.verify_ssl) as client:
            for i in range(cfg.repetitions):
                attempt = await _single_attempt(client, cfg.target_url, cfg, reference_body)
                result.attempts.append(attempt)
                if attempt["ok"]:
                    sim_pct = round(attempt["similarity"] * 100)
                    log_fn(f"[{proxy_url}] attempt {i + 1}/{cfg.repetitions}: OK "
                           f"(similarity {sim_pct}%, {attempt['latency']:.2f}s)")
                else:
                    log_fn(f"[{proxy_url}] attempt {i + 1}/{cfg.repetitions}: FAILED "
                           f"({attempt['reason']})")
                if cfg.delay_ms and i < cfg.repetitions - 1:
                    await asyncio.sleep(cfg.delay_ms / 1000)
    except Exception as e:
        result.attempts.append({"ok": False, "latency": None, "status": None,
                                 "reason": f"client_error:{str(e)[:120]}", "similarity": None})
        log_fn(f"[{proxy_url}] error creating client: {str(e)[:120]}")

    s = result.summary
    log_fn(f"[{proxy_url}] completed: {s['passed']}/{s['total_requests']} "
           f"({round(s['success_rate'] * 100)}%)")
    return result


async def test_proxy_playwright(proxy_url: str, cfg: TestConfig, reference_body: str, log_fn) -> ProxyResult:
    result = ProxyResult(proxy=proxy_url)
    log_fn(f"[{proxy_url}] starting Playwright headless browser test ({cfg.repetitions}x)")
    proxy_config = parse_playwright_proxy(proxy_url)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, proxy=proxy_config)
            try:
                for i in range(cfg.repetitions):
                    start = time.monotonic()
                    try:
                        context = await browser.new_context(ignore_https_errors=not cfg.verify_ssl)
                        page = await context.new_page()
                        response = await page.goto(cfg.target_url, timeout=int(cfg.timeout_s * 1000), wait_until="load")
                        body = await page.content()
                        status_code = response.status if response else 200
                        elapsed = time.monotonic() - start
                        await context.close()
                        ok, similarity, reason = evaluate_response(status_code, body, reference_body, cfg.similarity_threshold)
                        attempt = {"ok": ok, "latency": elapsed, "status": status_code, "reason": reason, "similarity": similarity}
                    except Exception as e:
                        elapsed = time.monotonic() - start
                        err_str = str(e)
                        if "Timeout" in err_str or "timeout" in err_str:
                            reason = "timeout"
                        elif "ERR_CONNECTION" in err_str or "Connection" in err_str:
                            reason = "connection_error"
                        else:
                            reason = f"error:{err_str[:120]}"
                        attempt = {"ok": False, "latency": elapsed, "status": None, "reason": reason, "similarity": None}

                    result.attempts.append(attempt)
                    if attempt["ok"]:
                        sim_pct = round(attempt["similarity"] * 100)
                        log_fn(f"[{proxy_url}] attempt {i + 1}/{cfg.repetitions}: OK (similarity {sim_pct}%, {attempt['latency']:.2f}s)")
                    else:
                        log_fn(f"[{proxy_url}] attempt {i + 1}/{cfg.repetitions}: FAILED ({attempt['reason']})")
                    if cfg.delay_ms and i < cfg.repetitions - 1:
                        await asyncio.sleep(cfg.delay_ms / 1000)
            finally:
                await browser.close()
    except Exception as e:
        result.attempts.append({"ok": False, "latency": None, "status": None,
                                 "reason": f"client_error:{str(e)[:120]}", "similarity": None})
        log_fn(f"[{proxy_url}] error creating Playwright browser: {str(e)[:120]}")

    s = result.summary
    log_fn(f"[{proxy_url}] completed: {s['passed']}/{s['total_requests']} ({round(s['success_rate'] * 100)}%)")
    return result


@dataclass
class Job:
    id: str
    proxies: list
    config: TestConfig
    status: str = "running"  # running | done | cancelled | error
    error: str = ""
    completed: int = 0
    results: dict = field(default_factory=dict)
    log: list = field(default_factory=list)
    _task: object = None

    def log_event(self, message: str):
        self.log.append(message)
        if len(self.log) > MAX_LOG_ENTRIES:
            del self.log[: len(self.log) - MAX_LOG_ENTRIES]


class JobStore:
    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create(self, proxies: list[str], config: TestConfig) -> Job:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, proxies=proxies, config=config)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def run(self, job: Job):
        if job.config.engine == "playwright":
            job.log_event(f"Downloading reference page via Playwright (without proxy): {job.config.target_url}")
            try:
                reference_body = await fetch_reference_playwright(job.config)
            except Exception as e:
                job.status = "error"
                job.error = f"Failed to download reference page via Playwright: {str(e)[:200]}"
                job.log_event(f"ERROR downloading reference: {job.error}")
                return
        else:
            job.log_event(f"Downloading reference page via HTTP (without proxy): {job.config.target_url}")
            try:
                reference_body = await fetch_reference(job.config)
            except Exception as e:
                job.status = "error"
                job.error = f"Failed to download reference page (without proxy): {str(e)[:200]}"
                job.log_event(f"ERROR downloading reference: {job.error}")
                return

        job.log_event(f"Reference page downloaded successfully ({len(reference_body)} bytes).")
        job.log_event(f"Starting test for {len(job.proxies)} proxies using [{job.config.engine}] engine "
                       f"(concurrency {job.config.concurrency}, N={job.config.repetitions}).")

        sem = asyncio.Semaphore(max(1, job.config.concurrency))

        async def worker(proxy: str):
            async with sem:
                if job.status == "cancelled":
                    return
                if job.config.engine == "playwright":
                    res = await test_proxy_playwright(proxy, job.config, reference_body, job.log_event)
                else:
                    res = await test_proxy(proxy, job.config, reference_body, job.log_event)
                job.results[proxy] = res.summary
                job.completed += 1

        tasks = [asyncio.create_task(worker(p)) for p in job.proxies]
        job._task = tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        if job.status != "cancelled":
            job.status = "done"
            job.log_event("Test completed.")
        else:
            job.log_event("Test cancelled by user.")

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        job.status = "cancelled"
        if job._task:
            for t in job._task:
                t.cancel()
        return True


jobs = JobStore()
