# 🚀 ProxyTester

O **ProxyTester** é uma ferramenta local, leve e robusta projetada para testar e validar listas de proxies HTTP contra uma URL alvo configurável. Ao contrário de testadores simples que apenas validam o status code HTTP (o que é facilmente burlado por telas de bloqueio de bots que retornam status 200), o ProxyTester faz uma validação profunda por **comparação de similaridade de conteúdo** contra uma referência real obtida sem proxy.

---

## 🏗️ Arquitetura

O sistema é dividido em duas partes principais, mantendo um design limpo e sem dependências externas complexas:

*   **Backend (`backend/`):** Construído em **Python** utilizando **FastAPI** e **httpx** assíncrono. É responsável pela execução das requisições via proxy (`httpx.AsyncClient(proxy=...)`), cálculo da similaridade do HTML e controle de concorrência.
*   **Frontend (`frontend/`):** Interface amigável e reativa em **HTML5, CSS3 e JavaScript (ES6) puros**, servida estaticamente pelo próprio backend FastAPI. Permite configurar o teste, colar as listas de proxy e acompanhar o progresso e logs em tempo real.

---

## ⚙️ Mecanismo de Validação e Parâmetros

### Como funciona a validação?
1. Antes de testar qualquer proxy, o backend faz o download da **URL alvo** diretamente (sem proxy) e armazena o corpo HTML completo como **Referência**.
2. Cada proxy é testado **N vezes** (Repetições) sequencialmente, respeitando um intervalo (Delay) configurado.
3. Para cada requisição feita pelo proxy, a resposta HTML obtida é comparada com a Referência usando o algoritmo `SequenceMatcher` da biblioteca padrão do Python (`difflib`).
4. Uma tentativa é considerada bem-sucedida somente se o status HTTP for de sucesso (2xx) e a similaridade do conteúdo for igual ou superior ao **Limiar de Similaridade** configurado (padrão de 90%).

### Principais Parâmetros
*   **Repetições ($N$):** Define quantas vezes cada proxy será testado. Essencial para verificar a estabilidade do proxy ao longo do tempo.
*   **URL Alvo:** O endereço de destino do teste.
*   **Concorrência:** Número de proxies testados simultaneamente.
*   **Delay (ms):** Intervalo de espera entre as repetições sequenciais de um mesmo proxy.
*   **Limiar de Similaridade:** Fração mínima (0 a 1) de correspondência com a página de referência para marcar o teste do proxy como OK.

---

## ⚡ Inicialização Rápida

O projeto vem com o script auto-configurável `start.sh` na raiz. Ele cria o ambiente virtual Python, instala as dependências e inicia o servidor automaticamente.

Para rodar o projeto, execute no terminal:

```bash
./start.sh
```

Depois, acesse a ferramenta no seu navegador: **[http://localhost:8000](http://localhost:8000)**

---

## 🔌 Documentação das APIs (Endpoints)

Abaixo estão descritos os endpoints da API REST do ProxyTester com os formatos de entrada e saída esperados, acompanhados de exemplos de chamadas em **cURL**, **Python** e **Node.js**.

### 1. Criar um Job de Teste (`POST /api/jobs`)
Inicia um processo de validação em background para uma lista de proxies informada.

*   **Payload (JSON):**
    *   `proxies_raw` (String, obrigatório): Lista de proxies separados por quebra de linha.
    *   `target_url` (String, padrão: `https://www.uol.com.br`): URL alvo do teste.
    *   `repetitions` (Integer, 1 a 50, padrão: `5`)
    *   `concurrency` (Integer, 1 a 50, padrão: `5`)
    *   `delay_ms` (Integer, 0 a 60000, padrão: `500`)
    *   `timeout_s` (Float, 0.1 a 120, padrão: `15.0`)
    *   `similarity_threshold` (Float, 0.0 a 1.0, padrão: `0.9`)
    *   `verify_ssl` (Boolean, padrão: `true`)

*   **Retorno (JSON):**
    ```json
    {
      "job_id": "31f478a2e1d749969248cb1551a34db2",
      "total": 2
    }
    ```

#### Exemplos de Chamada:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "proxies_raw": "185.199.229.156:7492\nhttp://usuario:senha@192.168.1.100:8080",
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
    "proxies_raw": "185.199.229.156:7492\nhttp://usuario:senha@192.168.1.100:8080",
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
  proxies_raw: "185.199.229.156:7492\nhttp://usuario:senha@192.168.1.100:8080",
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

### 2. Consultar Status do Job (`GET /api/jobs/{job_id}`)
Consulta o status atual, logs em tempo real e os resultados detalhados de cada proxy.

*   **Query Params:**
    *   `log_since` (Integer, opcional, padrão: `0`): Índice a partir do qual retornar os logs novos do job.

*   **Retorno (JSON):**
    ```json
    {
      "job_id": "31f478a2e1d749969248cb1551a34db2",
      "status": "done", // Estados: "running", "done", "cancelled", "error"
      "error": "",      // Mensagem de erro caso o status seja "error"
      "total": 2,       // Total de proxies no job
      "completed": 2,   // Quantidade de proxies já processados
      "results": [      // Lista com o resultado detalhado por proxy
        {
          "proxy": "http://185.199.229.156:7492",
          "total_requests": 3,
          "passed": 2,
          "failed": 1,
          "success_rate": 0.6667,
          "avg_similarity": 0.9412, // Média da similaridade do conteúdo nas tentativas válidas
          "total_time_s": 4.125,
          "avg_latency_s": 1.375,
          "min_latency_s": 0.912,
          "max_latency_s": 2.103,
          "failure_reasons": {      // Histórico de motivos de falhas nas tentativas
            "timeout": 1
          }
        }
      ],
      "log": [          // Lista de strings com eventos detalhados do job (incremental)
        "Baixando página de referência (sem proxy): https://www.google.com",
        "Referência baixada com sucesso (14520 bytes).",
        "Teste concluído."
      ],
      "log_total": 3    // Quantidade total de linhas geradas no log até o momento
    }
    ```

#### Exemplos de Chamada:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X GET "http://localhost:8000/api/jobs/SEU_JOB_ID?log_since=0"
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

job_id = "SEU_JOB_ID"
response = requests.get(f"http://localhost:8000/api/jobs/{job_id}?log_since=0")
data = response.json()

print(f"Status: {data['status']}")
print(f"Progresso: {data['completed']}/{data['total']}")
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const jobId = "SEU_JOB_ID";

fetch(`http://localhost:8000/api/jobs/${jobId}?log_since=0`)
  .then(res => res.json())
  .then(data => {
    console.log(`Status: ${data.status}`);
    console.log(`Progresso: ${data.completed}/${data.total}`);
  });
```
</details>

---

### 3. Cancelar um Job (`POST /api/jobs/{job_id}/cancel`)
Interrompe a execução de um teste que ainda está em andamento.

*   **Retorno (JSON):**
    ```json
    {
      "status": "cancelled"
    }
    ```

#### Exemplos de Chamada:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST http://localhost:8000/api/jobs/SEU_JOB_ID/cancel
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

job_id = "SEU_JOB_ID"
response = requests.post(f"http://localhost:8000/api/jobs/{job_id}/cancel")
print(response.json())
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const jobId = "SEU_JOB_ID";

fetch(`http://localhost:8000/api/jobs/${jobId}/cancel`, { method: 'POST' })
  .then(res => res.json())
  .then(data => console.log(data));
```
</details>

---

### 4. Exportar Proxies Aprovados (`GET /api/jobs/{job_id}/export`)
Retorna uma lista de proxies aprovados em formato de texto puro (`text/plain`), filtrada por uma taxa de sucesso mínima.

*   **Query Params:**
    *   `threshold` (Float, opcional, padrão: `0.8`): Taxa de sucesso mínima (ex: `0.8` exige no mínimo 80% de requisições bem-sucedidas nas repetições).

*   **Retorno (`text/plain`):**
    ```text
    http://185.199.229.156:7492
    http://usuario:senha@192.168.1.100:8080
    ```

#### Exemplos de Chamada:

<details>
<summary><b>cURL</b></summary>

```bash
curl -X GET "http://localhost:8000/api/jobs/SEU_JOB_ID/export?threshold=0.8"
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

job_id = "SEU_JOB_ID"
response = requests.get(f"http://localhost:8000/api/jobs/{job_id}/export?threshold=0.8")
proxies_aprovados = response.text
print(proxies_aprovados)
```
</details>

<details>
<summary><b>Node.js (Fetch)</b></summary>

```javascript
const jobId = "SEU_JOB_ID";

fetch(`http://localhost:8000/api/jobs/${jobId}/export?threshold=0.8`)
  .then(res => res.text())
  .then(text => console.log("Proxies aprovados:\n", text));
```
</details>

---

## 📝 Formato das Listas de Proxies
Ao inserir proxies, o formato aceito inclui:
*   `http://usuario:senha@ip:porta`
*   `http://ip:porta`
*   `ip:porta` (o protocolo `http://` é adicionado de forma implícita)

*Linhas em branco ou iniciadas por `#` são automaticamente ignoradas pelo parser.*
