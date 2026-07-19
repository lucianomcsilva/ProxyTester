# 🚀 ProxyTester

**ProxyTester** is a lightweight, local, and robust tool designed to test and validate HTTP proxy lists against a configurable target URL. Unlike naive testers that only check HTTP status codes (which are easily bypassed by bot-blocking screens returning a 200 OK status), ProxyTester performs deep validation using **content similarity comparison** against a real baseline page fetched without a proxy.

---

## 🏗️ Architecture

The system is divided into two main components, keeping a clean design without complex external dependencies:

*   **Backend (`backend/`):** Built in **Python** using **FastAPI** and asynchronous **httpx**. It executes proxy requests (`httpx.AsyncClient(proxy=...)`), calculates HTML similarity, and manages concurrency.
*   **Frontend (`frontend/`):** A responsive and friendly UI built with **vanilla HTML5, CSS3, and JavaScript (ES6)**, served statically by the FastAPI backend itself. Allows configuring tests, pasting proxy lists, and tracking real-time execution logs and progress.

---

## ⚙️ Validation Mechanism & Parameters

### How does validation work?
1. Before testing any proxy, the backend downloads the **Target URL** directly (without proxy) and stores the full HTML body as the **Reference**.
2. Each proxy is tested **N times** (Repetitions) sequentially, respecting a configured interval (Delay).
3. For each request performed via proxy, the response HTML is compared to the Reference using Python's standard library `SequenceMatcher` (`difflib`).
4. An attempt is marked as successful only if the HTTP status is successful (2xx) and the content similarity is greater than or equal to the configured **Similarity Threshold** (default 90%).

### Key Parameters
*   **Repetitions ($N$):** Number of times each proxy is tested. Essential for checking proxy consistency over time.
*   **Target URL:** Destination webpage for testing.
*   **Concurrency:** Number of proxies tested in parallel.
*   **Delay (ms):** Wait time between sequential requests for the same proxy.
*   **Similarity Threshold:** Minimum ratio (0 to 1) of matching content with the reference page to mark a proxy attempt as OK.

---

## ⚡ Quick Start

The project includes an auto-configuring `start.sh` script in the root directory. It automatically sets up the Python virtual environment, installs dependencies, and starts the server.

To run the project, execute in your terminal:

```bash
./start.sh
```

Then open your browser at: **[http://localhost:8000](http://localhost:8000)**

---

## 🔌 API Documentation (Endpoints)

Below are the REST API endpoints provided by ProxyTester with request/response schemas and code examples in **cURL**, **Python**, and **Node.js**.

### 1. Create a Test Job (`POST /api/jobs`)
Initiates a background validation process for a provided proxy list.

*   **Request Body (JSON):**
    *   `proxies_raw` (String, required): Line-separated list of proxies.
    *   `target_url` (String, default: `https://www.uol.com.br`): Target URL to test.
    *   `repetitions` (Integer, 1 to 50, default: `5`)
    *   `concurrency` (Integer, 1 to 50, default: `5`)
    *   `delay_ms` (Integer, 0 to 60000, default: `500`)
    *   `timeout_s` (Float, 0.1 to 120, default: `15.0`)
    *   `similarity_threshold` (Float, 0.0 to 1.0, default: `0.9`)
    *   `verify_ssl` (Boolean, default: `true`)

*   **Response (JSON):**
    ```json
    {
      "job_id": "31f478a2e1d749969248cb1551a34db2",
      "total": 2
    }
    ```

#### Request Examples:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "proxies_raw": "185.199.229.156:7492\nhttp://user:pass@192.168.1.100:8080",
    "target_url": "https://www.google.com",
    "repetitions": 3,
    "concurrency": 2,
    "delay_ms": 200,
    "timeout_s": 10.0,
    "similarity_threshold": 0.85,
    "verify_ssl": true
  }'
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

url = "http://localhost:8000/api/jobs"
payload = {
    "proxies_raw": "185.199.229.156:7492\nhttp://user:pass@192.168.1.100:8080",
    "target_url": "https://www.google.com",
    "repetitions": 3,
    "concurrency": 2,
    "delay_ms": 200,
    "timeout_s": 10.0,
    "similarity_threshold": 0.85,
    "verify_ssl": True
}

response = requests.post(url, json=payload)
print(response.json())
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const payload = {
  proxies_raw: "185.199.229.156:7492\nhttp://user:pass@192.168.1.100:8080",
  target_url: "https://www.google.com",
  repetitions: 3,
  concurrency: 2,
  delay_ms: 200,
  timeout_s: 10.0,
  similarity_threshold: 0.85,
  verify_ssl: true
};

fetch('http://localhost:8000/api/jobs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));
```
</details>

---

### 2. Get Job Status (`GET /api/jobs/{job_id}`)
Retrieves current status, real-time logs, and detailed per-proxy results.

*   **Query Params:**
    *   `log_since` (Integer, optional, default: `0`): Log array index to fetch incremental log lines.

*   **Response (JSON):**
    ```json
    {
      "job_id": "31f478a2e1d749969248cb1551a34db2",
      "status": "done", // Possible statuses: "running", "done", "cancelled", "error"
      "error": "",      // Error message if status is "error"
      "total": 2,       // Total proxies in job
      "completed": 2,   // Number of proxies completed so far
      "results": [      // Detailed per-proxy summary list
        {
          "proxy": "http://185.199.229.156:7492",
          "total_requests": 3,
          "passed": 2,
          "failed": 1,
          "success_rate": 0.6667,
          "avg_similarity": 0.9412, // Average content similarity ratio for valid responses
          "total_time_s": 4.125,
          "avg_latency_s": 1.375,
          "min_latency_s": 0.912,
          "max_latency_s": 2.103,
          "failure_reasons": {      // Count of failure reasons encountered
            "timeout": 1
          }
        }
      ],
      "log": [          // Incremental log events
        "Downloading reference page (without proxy): https://www.google.com",
        "Reference page downloaded successfully (14520 bytes).",
        "Test completed."
      ],
      "log_total": 3    // Total lines produced in log so far
    }
    ```

#### Request Examples:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X GET "http://localhost:8000/api/jobs/YOUR_JOB_ID?log_since=0"
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

job_id = "YOUR_JOB_ID"
response = requests.get(f"http://localhost:8000/api/jobs/{job_id}?log_since=0")
data = response.json()

print(f"Status: {data['status']}")
print(f"Progress: {data['completed']}/{data['total']}")
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const jobId = "YOUR_JOB_ID";

fetch(`http://localhost:8000/api/jobs/${jobId}?log_since=0`)
  .then(res => res.json())
  .then(data => {
    console.log(`Status: ${data.status}`);
    console.log(`Progress: ${data.completed}/${data.total}`);
  });
```
</details>

---

### 3. Cancel a Job (`POST /api/jobs/{job_id}/cancel`)
Stops an ongoing proxy test job.

*   **Response (JSON):**
    ```json
    {
      "status": "cancelled"
    }
    ```

#### Request Examples:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST http://localhost:8000/api/jobs/YOUR_JOB_ID/cancel
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

job_id = "YOUR_JOB_ID"
response = requests.post(f"http://localhost:8000/api/jobs/{job_id}/cancel")
print(response.json())
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const jobId = "YOUR_JOB_ID";

fetch(`http://localhost:8000/api/jobs/${jobId}/cancel`, { method: 'POST' })
  .then(res => res.json())
  .then(data => console.log(data));
```
</details>

---

### 4. Export Passing Proxies (`GET /api/jobs/{job_id}/export`)
Exports approved proxies in plain text (`text/plain`), filtered by a minimum success rate.

*   **Query Params:**
    *   `threshold` (Float, optional, default: `0.8`): Minimum required success rate (e.g. `0.8` requires at least 80% passing attempts).

*   **Response (`text/plain`):**
    ```text
    http://185.199.229.156:7492
    http://user:pass@192.168.1.100:8080
    ```

#### Request Examples:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X GET "http://localhost:8000/api/jobs/YOUR_JOB_ID/export?threshold=0.8"
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

job_id = "YOUR_JOB_ID"
response = requests.get(f"http://localhost:8000/api/jobs/{job_id}/export?threshold=0.8")
passing_proxies = response.text
print(passing_proxies)
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const jobId = "YOUR_JOB_ID";

fetch(`http://localhost:8000/api/jobs/${jobId}/export?threshold=0.8`)
  .then(res => res.text())
  .then(text => console.log("Passing proxies:\n", text));
```
</details>

---

## 📝 Proxy List Format
Accepted input formats include:
*   `http://user:pass@ip:port`
*   `http://ip:port`
*   `ip:port` (`http://` scheme is added automatically)

*Blank lines and lines starting with `#` are automatically ignored.*

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
