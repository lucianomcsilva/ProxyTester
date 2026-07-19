const $ = (id) => document.getElementById(id);

let currentJobId = null;
let pollTimer = null;
let lastResults = [];
let logCursor = 0;

$("submit-btn").addEventListener("click", startJob);
$("cancel-btn").addEventListener("click", cancelJob);
$("export-btn").addEventListener("click", exportPassing);

async function startJob() {
  const body = {
    proxies_raw: $("proxies").value,
    target_url: $("target_url").value,
    repetitions: parseInt($("repetitions").value, 10),
    concurrency: parseInt($("concurrency").value, 10),
    delay_ms: parseInt($("delay_ms").value, 10),
    timeout_s: parseFloat($("timeout_s").value),
    similarity_threshold: (parseFloat($("similarity_threshold").value) || 0) / 100,
    verify_ssl: $("verify_ssl").checked,
  };

  if (!body.proxies_raw.trim()) return alert("Please paste at least one proxy.");
  if (!body.target_url.trim()) return alert("Please provide a target URL.");

  setBusy(true);
  $("results-panel").hidden = true;
  $("progress-panel").hidden = false;
  setProgress(0, 0);
  logCursor = 0;
  $("log-panel").innerHTML = "";

  let res;
  try {
    res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    setBusy(false);
    return alert("Failed to connect to local backend.");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    setBusy(false);
    return alert("Error: " + err.detail);
  }

  const data = await res.json();
  currentJobId = data.job_id;
  pollJob(data.total);
}

function pollJob(total) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const res = await fetch(`/api/jobs/${currentJobId}?log_since=${logCursor}`);
    if (!res.ok) return;
    const job = await res.json();
    setProgress(job.completed, job.total);
    appendLog(job.log);
    logCursor = job.log_total;

    if (job.status === "error") {
      clearInterval(pollTimer);
      setBusy(false);
      alert("Error: " + job.error);
      return;
    }
    if (job.status === "done" || job.status === "cancelled") {
      clearInterval(pollTimer);
      setBusy(false);
      lastResults = job.results;
      renderResults(job.results);
    }
  }, 800);
}

function appendLog(lines) {
  if (!lines || !lines.length) return;
  const panel = $("log-panel");
  const frag = document.createDocumentFragment();
  for (const line of lines) {
    const div = document.createElement("div");
    div.className = "log-line " + classifyLogLine(line);
    div.textContent = line;
    frag.appendChild(div);
  }
  panel.appendChild(frag);
  if ($("autoscroll").checked) {
    panel.scrollTop = panel.scrollHeight;
  }
}

function classifyLogLine(line) {
  const concluded = line.match(/completed: (\d+)\/(\d+)/);
  if (concluded) {
    return concluded[1] === "0" ? "fail" : "ok";
  }
  if (line.includes(": OK") || line.includes("downloaded successfully")) return "ok";
  if (line.includes("FAILED") || line.startsWith("ERROR")) return "fail";
  return "info";
}

async function cancelJob() {
  if (!currentJobId) return;
  await fetch(`/api/jobs/${currentJobId}/cancel`, { method: "POST" });
}

function setBusy(busy) {
  $("submit-btn").disabled = busy;
  $("cancel-btn").disabled = !busy;
}

function setProgress(completed, total) {
  const pct = total ? Math.round((completed / total) * 100) : 0;
  $("progress-bar").style.width = pct + "%";
  $("progress-text").textContent = `${completed} / ${total} proxies tested (${pct}%)`;
}

function rateClass(rate) {
  if (rate >= 0.7) return "";
  if (rate >= 0.4) return "mid";
  return "low";
}

function renderResults(results) {
  const sorted = [...results].sort((a, b) => b.success_rate - a.success_rate);
  const tbody = document.querySelector("#results-table tbody");
  tbody.innerHTML = "";

  for (const r of sorted) {
    const tr = document.createElement("tr");
    const pct = Math.round(r.success_rate * 100);
    const reasons = Object.entries(r.failure_reasons || {})
      .map(([reason, count]) => `<span class="reason-chip">${reason} x${count}</span>`)
      .join("");

    const simPct = r.avg_similarity === null || r.avg_similarity === undefined
      ? "—" : Math.round(r.avg_similarity * 100) + "%";

    tr.innerHTML = `
      <td class="proxy-cell">${escapeHtml(r.proxy)}</td>
      <td><span class="rate-bar"><span class="rate-fill ${rateClass(r.success_rate)}" style="width:${pct}%"></span></span>${pct}%</td>
      <td>${r.passed} / ${r.total_requests}</td>
      <td>${simPct}</td>
      <td>${fmt(r.avg_latency_s)} / ${fmt(r.min_latency_s)} / ${fmt(r.max_latency_s)}</td>
      <td>${fmt(r.total_time_s)}</td>
      <td>${reasons || "—"}</td>
    `;
    tbody.appendChild(tr);
  }

  $("results-panel").hidden = false;
}

function fmt(v) {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

async function exportPassing() {
  const thresholdPct = parseFloat($("threshold").value) || 0;
  const threshold = thresholdPct / 100;
  const passing = lastResults
    .filter((r) => r.success_rate >= threshold)
    .map((r) => r.proxy);

  if (!passing.length) {
    $("export-status").textContent = "No proxies met the threshold.";
    return;
  }

  const text = passing.join("\n");
  try {
    await navigator.clipboard.writeText(text);
    $("export-status").textContent = `${passing.length} proxies copied.`;
  } catch {
    $("export-status").textContent = "Could not copy automatically.";
    console.log(text);
  }
  setTimeout(() => ($("export-status").textContent = ""), 4000);
}
