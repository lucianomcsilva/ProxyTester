"""ProxyTester backend — FastAPI app serving the API and the static frontend."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from proxy_tester import TestConfig, jobs, parse_proxies

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title="ProxyTester")


class TestRequest(BaseModel):
    proxies_raw: str
    target_url: str = "https://www.uol.com.br"
    repetitions: int = Field(5, ge=1, le=50)
    concurrency: int = Field(5, ge=1, le=50)
    delay_ms: int = Field(500, ge=0, le=60_000)
    timeout_s: float = Field(15.0, gt=0, le=120)
    similarity_threshold: float = Field(0.9, ge=0, le=1)
    verify_ssl: bool = True


@app.post("/api/jobs")
async def create_job(req: TestRequest):
    proxies = parse_proxies(req.proxies_raw)
    if not proxies:
        raise HTTPException(400, "Nenhum proxy válido encontrado na lista.")
    if not req.target_url.strip():
        raise HTTPException(400, "URL alvo é obrigatória.")

    cfg = TestConfig(
        target_url=req.target_url.strip(),
        repetitions=req.repetitions,
        concurrency=req.concurrency,
        delay_ms=req.delay_ms,
        timeout_s=req.timeout_s,
        similarity_threshold=req.similarity_threshold,
        verify_ssl=req.verify_ssl,
    )
    job = jobs.create(proxies, cfg)
    asyncio.create_task(jobs.run(job))
    return {"job_id": job.id, "total": len(proxies)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, log_since: int = 0):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    return {
        "job_id": job.id,
        "status": job.status,
        "error": job.error,
        "total": len(job.proxies),
        "completed": job.completed,
        "results": list(job.results.values()),
        "log": job.log[log_since:],
        "log_total": len(job.log),
    }


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    if not jobs.cancel(job_id):
        raise HTTPException(404, "Job não encontrado.")
    return {"status": "cancelled"}


@app.get("/api/jobs/{job_id}/export", response_class=PlainTextResponse)
async def export_job(job_id: str, threshold: float = 0.8):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    lines = [r["proxy"] for r in job.results.values() if r["success_rate"] >= threshold]
    return "\n".join(lines)


# Static frontend last, so it doesn't shadow the /api routes above.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
