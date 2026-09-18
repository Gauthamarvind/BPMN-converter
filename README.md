# Process2BPMN

**Process2BPMN** is an intelligent, vendor-agnostic pipeline and web application that converts unstructured natural language process descriptions into standards-compliant, syntactically valid, and cleanly laid out **BPMN 2.0** diagrams.

Whether you have Standard Operating Procedures (SOPs), meeting notes, interview transcripts, tabular spreadsheets, Word documents, or audio subtitles (VTT/SRT), Process2BPMN extracts activities, events, gateways, roles, and sequences, runs graph validation and auto-repair, calculates Sugiyama layered layout coordinates, and exports vendor-tailored BPMN 2.0 XML.

---

## Key Features

- **Multi-Format Ingestion**: Supports `.docx`, `.xlsx`, `.pdf`, `.csv`, `.md`, `.txt`, and `.vtt`/`.srt` transcripts.
- **Enterprise BPMN 2.0 Compatibility**: Generates valid BPMN 2.0 XML validated against official OMG BPMN 2.0 XSD schemas.
- **Vendor Export Profiles**: Tailors XML namespaces and Diagram Interchange (DI) attributes for **Generic BPMN 2.0**, **SAP Signavio**, **Camunda 7 & 8**, **Celonis**, and **Software AG ARIS**.
- **Deterministic Layout Engine**: Multi-lane Sugiyama layered layout algorithm with cycle breaking, crossing minimization, and coordinate assignment.
- **Vendor-Agnostic LLM Architecture**: Works with local models (Ollama, vLLM, LM Studio) or hosted cloud APIs (OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini, Groq, OpenRouter), plus a zero-network deterministic Mock provider.
- **Interactive No-Code Step Builder**: Capture, edit, reorder, and convert structured process steps directly in the browser.
- **Pre-Formatted Process Capture Templates**: Downloadable Excel (`.xlsx`) and Word (`.docx`) interview templates with automatic column mapping.

---

## Prerequisites

- **Python**: 3.10 or newer (with `pip`)
- **Node.js**: 18 or newer (with `npm` or `bun`)
- **Optional**: Docker & Docker Compose for containerized deployment

---

## Quick Start & Running the App

### 1. Development Mode (`make dev`)

In development mode, Vite runs on port `3000` with hot-module reloading and proxies all `/api/*` requests to the FastAPI backend running on port `8000`:

```bash
# Install dependencies & start both backend and frontend in dev mode
make dev
```

Visit `http://localhost:3000` to access the interactive web application.

### 2. Production / Single-Server Mode (`make run`)

Builds the frontend production bundle and serves both the SPA and FastAPI REST API from a single uvicorn instance on port `8000`:

```bash
make run
```

Visit `http://localhost:8000` in your browser.

---

## Docker Deployment

### Using Docker

```bash
# Build multi-stage Docker image
make docker-build
# or: docker build -t process2bpmn .

# Run container on port 8000
make docker-run
# or: docker run -d -p 8000:8000 --env-file .env --name process2bpmn process2bpmn
```

### Using Docker Compose

```bash
# Start with persistent volume for custom templates and environment configuration
docker compose up -d
```

The container mounts `./data` into `/app/data` to persist custom uploaded BPMN reference templates across container restarts.

---

## Choosing a model (read this first)

The server reads its model settings from `.env` at startup — the template `.env.example` has one
block per provider (Gemini, Ollama, OpenAI-compatible, Azure, Anthropic, mock). Restart after editing.

Two things in the app make this painless:

- The **model pill** in the toolbar shows what the next conversion will use (green dot = ready,
  red = no API key, grey = rule engine). Click it to open Settings.
- **Settings → Test connection** sends one tiny request to the model and shows either the latency
  or the exact error (unreachable endpoint, rejected key, rate limit) without converting anything.

Settings overrides live in the browser for that session; the API key is never persisted. Leave the
provider on "Server default" to use `.env`.

Structured inputs — the fill-in Excel/Word template, the Step Builder and legacy step lists — never
call a model. Switching the target tool, reference template or lane mapping re-renders the diagram
from the extracted process (`POST /api/render`) instead of calling the model again.

## Switching LLM Providers & Models

Process2BPMN is fully vendor-agnostic and configured via environment variables. Configure your `.env` file (or copy from `.env.example`) to select your preferred provider:

### Core LLM Configuration Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | Active LLM adapter: `ollama`, `openai_compatible`, `anthropic`, `gemini`, or `mock` | `ollama` |
| `LLM_MODEL` | Model name or deployment ID | `llama3` |
| `LLM_BASE_URL` | Base API URL for chat completions | `http://localhost:11434/v1` |
| `LLM_API_KEY` | API Key or authentication token | `ollama` |
| `LLM_AUTH_HEADER` | Header name for authorization: `Authorization`, `api-key`, `x-api-key`, or `x-goog-api-key` | `Authorization` |
| `LLM_CONTEXT_TOKENS` | Token window size for intelligent chunking | `8192` |
| `LLM_MAX_OUTPUT_TOKENS`| Maximum output tokens per generation request | `4096` |
| `LLM_TEMPERATURE` | Generation temperature | `0.1` |

---

### Provider Examples

#### 1. Ollama (Default — Fully Local & Offline)
```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_AUTH_HEADER=Authorization
LLM_CONTEXT_TOKENS=8192
```

#### 2. OpenAI / OpenAI-Compatible (OpenAI, Groq, OpenRouter, vLLM)
```env
LLM_PROVIDER=openai_compatible
LLM_MODEL=gpt-4o
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-proj-your-api-key-here
LLM_AUTH_HEADER=Authorization
LLM_CONTEXT_TOKENS=16384
```

#### 3. Azure OpenAI
```env
LLM_PROVIDER=openai_compatible
LLM_MODEL=gpt-4o
LLM_BASE_URL=https://your-resource-name.openai.azure.com/openai/deployments/your-deployment-name/chat/completions?api-version=2024-02-15-preview
LLM_API_KEY=your-azure-api-key
LLM_AUTH_HEADER=api-key
LLM_CONTEXT_TOKENS=16384
```

#### 4. Anthropic Claude
```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_API_KEY=sk-ant-your-anthropic-api-key
LLM_AUTH_HEADER=x-api-key
LLM_CONTEXT_TOKENS=16384
```

#### 5. Google Gemini
```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
LLM_API_KEY=your-gemini-api-key
LLM_AUTH_HEADER=x-goog-api-key
LLM_CONTEXT_TOKENS=16384
```

#### 6. Mock Provider (Zero Network / Offline Testing)
```env
LLM_PROVIDER=mock
LLM_MODEL=mock-model
LLM_BASE_URL=http://mock
LLM_API_KEY=mock
```

---

## Single Pool Collaboration Mode (`SINGLE_POOL`)

- `SINGLE_POOL=true` *(Default)*: Consolidates all identified participant roles into swimlanes within a **single collaboration pool**. This is standard for enterprise BPMN modeling where internal actors interact within a single process scope.
- `SINGLE_POOL=false`: Generates distinct participant pools for each role with message flows connecting across pool boundaries.

---

## Process Capture Templates & Samples

- **Downloadable Capture Forms**:
  - `Process_Capture_Template.xlsx` & `Process_Capture_Template_Example.xlsx`: Structured Excel workbooks with columns for Step #, Activity Name, Role / Swimlane, Step Type (Task, Decision, Event), Decision Target / Outcomes, and Description.
  - `Process_Capture_Template.docx` & `Process_Capture_Template_Example.docx`: Formatted Word documents for Standard Operating Procedures.
- **Sample Workflows**: Pre-loaded examples in `samples/` covering Leave Requests, Incident Resolution, Employee Onboarding, Customer Support Tickets, and Procurement Approvals.
- **Interactive Step Builder**: Built-in visual table editor to capture process steps without leaving the browser and generate diagrams instantly.

---

## Vendor Export Profiles

Process2BPMN tailors XML namespaces and BPMNDI layout structures for major process modeling platforms:

| Profile | Target System | Namespace / Attributes |
| :--- | :--- | :--- |
| **Generic** | Standard BPMN 2.0 | Standard OMG BPMN 2.0 (`http://www.omg.org/spec/BPMN/20100524/MODEL`) |
| **Signavio** | SAP Signavio Process Manager | Signavio namespace extensions, `sid-*` ID prefixes, custom style tags |
| **Camunda** | Camunda Platform 7 & 8 | Camunda namespace (`http://camunda.org/schema/1.0/bpmn`), execution properties |
| **Celonis** | Celonis Process Mining / Execution | Process mining activity identifiers, clean flow routing |
| **ARIS** | Software AG ARIS | Strict single-pool swimlane grouping, ARIS-compatible coordinates |

---

## Troubleshooting

| HTTP Status | Category | Root Cause & Resolution |
| :--- | :--- | :--- |
| **`502 Bad Gateway`** | **LLM Connection / Auth** | • Verify `LLM_BASE_URL` is reachable from the server.<br>• Check `LLM_API_KEY` validity and permissions.<br>• For Azure OpenAI, confirm `LLM_AUTH_HEADER=api-key` and deployment name in the URL.<br>• For Ollama, verify that the Ollama daemon is running (`ollama serve`) and the model is pulled (`ollama pull llama3`). |
| **`422 Unprocessable Entity`** | **Validation Failure** | • **XSD Validation Error**: The generated BPMN XML failed strict OMG BPMN 2.0 schema validation.<br>• **Template Row Error**: The uploaded Excel/Word table has conflicting sequence flows, invalid step numbers, or missing mandatory fields. |
| **`400 Bad Request`** | **Ingestion Error** | • Uploaded file is empty (0 bytes).<br>• Unsupported file format or file extension / magic-bytes mismatch.<br>• Scanned PDF with no extractable text layer.<br>• Encrypted or password-protected document. |

---

## Developer Commands

```bash
# Run all tests (pytest + frontend lint)
make test

# Run frontend TypeScript & design system lint
make lint

# Compile frontend bundle & template artifacts
make build

# Fetch official OMG BPMN 2.0 XSD schemas
make schemas

# Regenerate template assets
make templates
```
