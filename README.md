# Process2BPMN

**Process2BPMN** converts process descriptions — SOPs, meeting notes, transcripts, Word/Excel documents, filled-in capture forms — and BPMN files exported from other modelling tools into clean, standards-compliant **BPMN 2.0** diagrams that import directly into **Celonis** (default) or any standard BPMN 2.0 tool (bpmn.io, Bizagi, Flowable).

> **Scope v2 (September 2026).** The product has been narrowed to two export targets — Celonis and generic BPMN 2.0 — and gained a BPMN *import* path for files coming from other tools. The bundled sample workflows, the in-browser Step Builder and the Signavio/Camunda/ARIS export profiles have been removed. See [Roadmap](#roadmap-scope-v2) for what is done and what is in progress on branch `scope-celonis-v2`.

---

## Key Features

- **Multi-format ingestion**: `.docx`, `.xlsx`, `.pdf` (text layer), `.csv`, `.md`, `.txt`, `.json`, and `.vtt`/`.srt` transcripts, plus pasted text.
- **BPMN import from other tools**: upload a `.bpmn` / BPMN 2.0 `.xml` exported from Camunda Modeler, SAP Signavio, ARIS, Bizagi, Flowable or bpmn.io. Vendor-specific namespaces and extension elements are stripped, the graph is validated and repaired, and the result is re-exported as Celonis-ready or generic BPMN 2.0.
- **Process capture template**: one downloadable Excel (and Word) form with a single filled-in example. Filled forms are converted by rules — no language model involved.
- **Two export targets**: **Celonis** (default) and **Generic BPMN 2.0** (bpmn.io, Bizagi, Flowable, any OMG-compliant importer).
- **Strict BPMN 2.0 compliance**: every export is validated against the official OMG BPMN 2.0 XSD schemas.
- **Deterministic layout**: multi-lane Sugiyama layered layout with cycle breaking and crossing minimisation; imported diagrams keep their original coordinates when present.
- **Graph validation & auto-repair**: missing start/end events, dangling flows, unlabelled decision branches, unreachable steps; ERROR-level issues block export until fixed.
- **Vendor-agnostic language model**: local (Ollama, vLLM, LM Studio) or hosted (OpenAI, Azure OpenAI, Anthropic, Google Gemini, Groq, OpenRouter), plus an offline mock provider.
- **Reference BPMN templates**: upload your own Celonis/generic reference diagram to reuse its pools, lanes and namespaces; map extracted roles to its lanes.
- **Traceability**: every element links back to the sentence or table row it came from.
- **CLI** for batch conversion and CI use.

---

## Prerequisites

- **Python** 3.10 or newer (with `pip`)
- **Node.js** 18 or newer (with `npm`)
- **Optional**: Docker & Docker Compose

---

## Quick Start

### Development mode (`make dev`)

Vite serves the UI on port `3000` with hot reload and proxies `/api/*` to the FastAPI backend on port `8000`:

```bash
make dev
```

Open `http://localhost:3000`.

### Production / single-server mode (`make run`)

Builds the frontend and serves the SPA and the REST API from one uvicorn process on port `8000`:

```bash
make run
```

Open `http://localhost:8000`.

---

## Docker Deployment

```bash
# Build the multi-stage image
make docker-build            # or: docker build -t process2bpmn .

# Run on port 8000
make docker-run              # or: docker run -d -p 8000:8000 --env-file .env --name process2bpmn process2bpmn

# Or with Compose (persists ./data for uploaded reference templates)
docker compose up -d
```

---

## Feature Matrix & Execution Requirements

The table below outlines all available features in Process2BPMN, their execution methods, whether an LLM call is required, and the prerequisites to run them:

| Feature / Task | Requires LLM? | Supported Input Formats | Execution Methods | Requirements / Prerequisites | Output Artifacts |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Unstructured Document Conversion** | **Yes** (or `--mock`) | `.docx`, `.pdf` (text layer), `.md`, `.txt`, `.csv`, `.json`, pasted text | • Web UI: drag & drop or paste text<br>• CLI: `backend.cli convert`<br>• API: `POST /api/convert` | Configured LLM provider (`gemini`, `openai_compatible`, `anthropic`, `azure`, or local `ollama`) in `.env`, or use `--mock` for offline testing | Standards-compliant BPMN 2.0 XML with auto-layout, roles mapped to swimlanes, decisions, and end events |
| **Meeting & Interview Transcripts** | **Yes** (or `--mock`) | `.vtt`, `.srt`, transcript text | • Web UI: drop file or paste dialogue<br>• CLI: `backend.cli convert`<br>• API: `POST /api/convert` | Timestamp cues & speaker tags are automatically cleaned by parser; LLM or mock extracts sequence | Clean BPMN 2.0 diagram mapping conversational dialogue into chronological activities |
| **Process Capture Template Conversion** | **No** (100% Rule Engine) | `.xlsx`, `.docx` structured capture forms (using standard column headers) | • Web UI: drop `.xlsx` / `.docx`<br>• CLI: `backend.cli convert`<br>• API: `POST /api/convert` | Form must follow standard headers (`Step ID`, `Step`, `Responsible`, `Type`, `If Yes`, `If No`, `Parallel Group`, `Next Step`). No LLM required | Clean BPMN 2.0 XML with swimlanes, XOR gateways, and AND fork/join blocks |
| **Capture Form Row Diagnostics** | **No** (Deterministic) | `.xlsx`, `.docx`, `.csv`, `.json` capture tables | Built into parser on upload / CLI convert | None. Evaluates table contiguity, unhandled decision rows, duplicate IDs, and dangling next-steps | Detailed row-level error reports with row numbers and one-click fixes |
| **BPMN Import from External Tools** | **No** (100% Deterministic) | `.bpmn`, `.xml` from Camunda 7/8, SAP Signavio, ARIS, Bizagi, Flowable, bpmn.io | • Web UI: drop `.bpmn` file<br>• CLI: `backend.cli import`<br>• API: `POST /api/import/bpmn` | Valid BPMN 2.0 XML exported from external tool. No LLM required | Normalized Celonis / Generic BPMN 2.0 with vendor extensions stripped and original coordinates preserved |
| **Target Profile Re-rendering** | **No** (Zero LLM) | Existing in-memory process graph | • Web UI: toolbar target toggle<br>• API: `POST /api/render` | Extracted Process IR in session memory. Re-serializes directly from graph representation | Instantly switches between Celonis (single pool) and Generic BPMN 2.0 without re-calling model |
| **Reference Template & Lane Mapping** | **No** (Zero LLM) | `.bpmn` reference diagram + role-to-lane map | • Web UI: Templates menu<br>• API: `POST /api/templates/map-lanes`<br>• CLI: `--template` | Custom reference BPMN file uploaded to server (`data/templates/`) | Diagram formatted into reference template's pools and corporate swimlanes |
| **Sugiyama Auto-Layout & Cycle Breaking** | **No** (Deterministic) | Process IR graph | Built into conversion, render, and CLI import (`--relayout`) | None. Multi-lane Sugiyama engine breaks feedback cycles and routes return flows underneath lanes | Full BPMNDI diagram coordinates with clean, non-inverting horizontal flow |
| **Graph Validation & Auto-Repair** | **No** (Deterministic) | Process IR graph | Built into conversion and import pipeline | None. Synthesizes missing start/end events, cleans self-loops, and flags errors | Validated process graph; reports blocking issues vs informational auto-repairs |
| **Strict Export Gate Enforcement** | **No** (Deterministic) | Process IR + validation issues | • Web UI Export button<br>• CLI exit code 2<br>• API: `POST /api/export/*` | Process must be free of ERROR-level issues (e.g. unreachable tasks, unlabelled decisions). Override with `--force` | HTTP 422 if blocked; otherwise writes valid `.bpmn`, `.svg`, `.png`, or bulk `.zip` |
| **OMG BPMN 2.0 XSD Schema Validation** | **No** (Deterministic) | Generated BPMN XML | Built into all export routes and CLI commands | Official OMG BPMN 2.0 XSD schemas in `backend/schemas/` | Validates generated XML against official OMG schemas before any file is saved |

---

## When is a Language Model Called?

Understanding what requires a model call helps optimize costs, latency, and offline usage:

> [!IMPORTANT]
> **Operations that REQUIRE an LLM call:**
> - Converting unstructured, free-form prose (SOP manuals, policy handbooks, emails, meeting transcripts) where process logic must be interpreted and structured from natural language.
> - *Note*: You can completely bypass LLM calls for unstructured text during development or CI by passing `--mock` (CLI) or `mock=true` (API), which uses an offline deterministic rule engine.

> [!TIP]
> **Operations that NEVER call an LLM (100% Deterministic & Offline):**
> 1. **Structured Process Capture Templates**: Uploading `.xlsx` or `.docx` forms downloaded from the Template menu.
> 2. **BPMN Import from other tools**: Uploading `.bpmn` files from Camunda, Signavio, ARIS, Flowable, Bizagi, or bpmn.io.
> 3. **Export Target Switching**: Toggling between **Celonis** and **Generic BPMN 2.0** in the toolbar (`POST /api/render`).
> 4. **Reference Template Lane Mapping**: Binding process roles to standard enterprise lanes.
> 5. **Re-layout, Graph Validation & Export**: Sugiyama layout calculation, cycle breaking, XSD schema verification, and diagram downloads (`.bpmn`, `.svg`, `.png`, `.zip`).

---

## How to Use: Execution Modes & Workflows

### 1. Web Application (Interactive UI)

The page opens empty — nothing is preloaded and no model is called until you convert something.

#### A. Convert a document or pasted text
1. Drop a file (`.docx`, `.xlsx`, `.pdf`, `.csv`, `.md`, `.txt`, `.vtt`) onto the canvas or the left sidebar, or paste text.
2. The target tool is **Celonis** by default. Switch to **Generic BPMN 2.0** in the toolbar if you need a plain OMG file.
3. Click **Convert Process**.
4. Review the diagram; click any element to see its details and the source sentence it came from. The **Issues** tab lists warnings and anything that blocks export.
5. **Export** as `.bpmn`, `.svg`, `.png`, or a ZIP containing both Celonis and generic `.bpmn` files.

#### B. Import a BPMN file from another tool (Zero LLM)
1. Drop a `.bpmn` / `.xml` exported from Camunda, Signavio, ARIS, Bizagi, Flowable or bpmn.io onto the canvas or the sidebar. BPMN files are routed to the importer automatically.
2. The importer detects the source tool, removes vendor namespaces and extension elements, validates the graph, and renders the diagram. What it stripped, approximated, or dropped is listed under **Issues**. No model is called.
3. The diagram keeps the coordinates the source file carried. Click **Re-layout** on the status pill to replace them with a clean automatic layout.
4. Export as Celonis or generic BPMN 2.0 exactly as in flow A.

How to get a clean BPMN 2.0 export out of each tool:

| Source tool | Export action | Notes |
| :--- | :--- | :--- |
| Camunda Modeler 7/8 | File → Save As → `.bpmn` | Camunda namespace and `zeebe:` extensions are stripped. |
| SAP Signavio | Export → BPMN 2.0 XML | `sid-*` IDs are kept; Signavio styling tags are dropped. |
| Software AG ARIS | Export → BPMN 2.0 | ARIS attribute extensions are dropped. |
| Bizagi Modeler | Export/Import → Export to BPMN | Bizagi's native `.bpm` is not BPMN — export to `.bpmn` first. |
| Flowable | Export → BPMN 2.0 XML | `flowable:` extensions are dropped. |
| bpmn.io / other | Download `.bpmn` | Imported as-is. |

#### C. Use the process capture template (Zero LLM)
1. Open **Template** in the toolbar. One page shows the capture form and one filled-in example process.
2. Download the blank Excel (or Word) form, fill it in with your steps, and upload it like any other file.
3. The rows are converted by rules and any row problems are reported with the row number.

#### D. Reuse your own reference diagram (Zero LLM)
1. **Templates → Upload** a `.bpmn` reference diagram from Celonis or a generic tool.
2. Select it in the toolbar and, if needed, open **Lane mapping** to match your roles to its lanes.
3. Convert or re-render; the export uses the template's pools, lanes, and namespaces.

---

### 2. Command Line Interface (CLI)

The CLI provides full functionality for headless conversions, batch jobs, and CI/CD pipelines:

```bash
# A. Convert an SOP document using Celonis as the default export target
python3 -m backend.cli convert path/to/sop.docx -o converted/sop_celonis.bpmn

# B. Convert to Generic OMG BPMN 2.0 target
python3 -m backend.cli convert path/to/sop.docx -p generic -o converted/sop_generic.bpmn

# C. Convert offline using the deterministic rule engine (no LLM required)
python3 -m backend.cli convert path/to/sop.md --mock -o converted/sop_mock.bpmn

# D. Convert a structured Process Capture Excel form (zero LLM)
python3 -m backend.cli convert templates/Process_Capture_Template_Example.xlsx -o converted/capture.bpmn

# E. Import a foreign BPMN file (Camunda, Flowable, Signavio) and re-export for Celonis
python3 -m backend.cli import path/to/camunda_export.bpmn -o converted/celonis_ready.bpmn

# F. Import foreign BPMN and re-compute layout from scratch
python3 -m backend.cli import path/to/camunda_export.bpmn --relayout -o converted/celonis_relayout.bpmn

# G. Force export even when diagram has blocking ERROR-level validation issues
python3 -m backend.cli convert path/to/sop.txt --mock --force -o converted/inspection_only.bpmn

# H. List all available export profiles
python3 -m backend.cli profiles
```

*Exit Codes*:
- `0`: Success (file validated against OMG XSD and written).
- `2`: Export blocked due to ERROR-level graph issues (unreachable steps, unlabelled decisions). Override with `--force`.
- `1`: Ingestion error, file not found, or LLM connection failure.

---

### 3. REST API Endpoints

All core capabilities are exposed via REST API for custom integrations:

| Endpoint | Method | Requires LLM? | Description |
| :--- | :---: | :---: | :--- |
| `/api/convert` | `POST` | Yes (or `mock=true`) | Ingest document (`multipart/form-data`) and return BPMN XML, Process IR, and validation issues |
| `/api/import/bpmn` | `POST` | **No** | Ingest foreign BPMN XML; returns sanitized BPMN XML, Process IR, and stripped extension report |
| `/api/render` | `POST` | **No** | Re-render existing Process IR to a different profile (`celonis` or `generic`) or reference template |
| `/api/templates` | `GET`, `POST` | **No** | List uploaded reference templates or upload a new corporate BPMN reference diagram |
| `/api/templates/map-lanes` | `POST` | **No** | Map extracted process actors to reference template lane IDs |
| `/api/templates/download-blank` | `GET` | **No** | Download blank Excel/Word capture forms or example templates (`type=xlsx\|docx&sample=true\|false`) |
| `/api/export/bpmn` | `POST` | **No** | Export BPMN XML with strict validation (returns 422 if blocking errors exist) |
| `/api/export/bulk` | `POST` | **No** | Download multi-target ZIP bundle containing Celonis and Generic BPMN XML plus SVG diagrams |
| `/api/health` | `GET` | **No** | Service health status, active provider, and server configuration |
| `/api/llm/ping` | `POST` | Optional | Test connection latency and credential validity for configured or client-supplied LLM endpoint |

---

## Export Targets

| Target | Default | What it produces | Import into |
| :--- | :--- | :--- | :--- |
| **Celonis** | ✅ | BPMN 2.0 XML tuned for Celonis process import: single collaboration pool with swimlanes, clean activity identifiers, conditions on flows, no vendor extensions. | Celonis Process Designer / process import |
| **Generic BPMN 2.0** | | Plain OMG BPMN 2.0 (`http://www.omg.org/spec/BPMN/20100524/MODEL`) with full BPMNDI. | bpmn.io, Bizagi Modeler, Flowable, Camunda Modeler, Signavio, ARIS |

Both profiles live in `profiles/celonis.yaml` and `profiles/generic.yaml`.

---

## Choosing a model

The server reads its model settings from `.env` at startup — `.env.example` has one block per provider. Restart after editing.

- The **model pill** in the toolbar shows what the next conversion will use (green = ready, red = no API key, grey = rule engine). Click it to open Settings.
- **Settings → Test connection** sends one tiny request and shows either the latency or the exact error.
- Settings overrides live in the browser for the session; the API key is never persisted. Leave the provider on "Server default" to use `.env`.

Structured inputs — the filled-in capture form and imported BPMN files — never call a model. Switching the target tool, reference template or lane mapping re-renders from the extracted process (`POST /api/render`) instead of calling the model again.

### Core configuration variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `ollama`, `openai_compatible`, `anthropic`, `gemini`, `azure` or `mock` | `ollama` |
| `LLM_MODEL` | Model name or deployment ID | `llama3` |
| `LLM_BASE_URL` | Base API URL | `http://localhost:11434/v1` |
| `LLM_API_KEY` | API key or token | `ollama` |
| `LLM_AUTH_HEADER` | `Authorization`, `api-key`, `x-api-key` or `x-goog-api-key` | `Authorization` |
| `LLM_CONTEXT_TOKENS` | Context window used for chunking | `8192` |
| `LLM_MAX_OUTPUT_TOKENS` | Max output tokens per request | `4096` |
| `LLM_TEMPERATURE` | Generation temperature | `0.1` |
| `LLM_TIMEOUT` | Request timeout in seconds | `90` |
| `DEFAULT_PROFILE` | Export target used when none is given | `celonis` |
| `SINGLE_POOL` | `true` merges all roles into one pool with swimlanes (required for Celonis) | `true` |

### Provider examples

```env
# Ollama (local, offline)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama

# OpenAI / Groq / OpenRouter / vLLM / LM Studio
LLM_PROVIDER=openai_compatible
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...

# Azure OpenAI
LLM_PROVIDER=azure
LLM_MODEL=gpt-4o
LLM_BASE_URL=https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=2024-10-21
LLM_API_KEY=...
LLM_AUTH_HEADER=api-key

# Anthropic Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_BASE_URL=https://api.anthropic.com/v1
LLM_API_KEY=sk-ant-...

# Google Gemini
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
LLM_API_KEY=...

# Mock (no model; pipeline and importer testing only)
LLM_PROVIDER=mock
```

---

## Tests

| Layer | Command | What it covers |
| :--- | :--- | :--- |
| Backend | `pytest -v` | Pipeline, importer, export gate, profiles, template parsing, API contract |
| Design & types | `npm run lint` | Typography floor, design tokens, TypeScript |
| Frontend units | `npm run test` | Toolbar targets, Template page, upload routing, re-layout control (Vitest + Testing Library) |
| End to end | `npm run test:e2e` | Import a BPMN file, render, re-layout, export (Playwright, Chromium) |

`make test` runs the first three; `make test-e2e` builds the SPA, starts uvicorn and runs the
smoke test. CI runs all four on every push and pull request.

The e2e test deliberately uses the BPMN import path: it is deterministic, so the smoke test
cannot flake on model availability.

---

## Export gate

Conversion and import always return a diagram, but export (`/api/export/bpmn`, `/api/export/bulk`, the CLI) is refused while ERROR-level issues exist — unreachable steps, unlabelled decision branches, unbalanced parallel gateways, or template rows that conflict. Each exported file is XSD-validated before it is written. Fix the issues listed in the Inspector, or pass `--force` on the CLI.

---

## Deploying for a team

`backend/security.py` provides `APP_AUTH_MODE=none|proxy|token`, per-user rate limiting and concurrency slots, an SSRF guard on client-supplied `base_url`, and `ALLOW_CLIENT_LLM_OVERRIDES` to lock the model to the server's `.env`. Put the app behind a reverse proxy with SSO and TLS, set `APP_AUTH_MODE=proxy`, restrict `LLM_BASE_URL_ALLOWLIST`, and keep `.env` on the server only. Uploaded reference templates are stored per user under `./data`.

---

## Troubleshooting

| HTTP status | Category | Cause and fix |
| :--- | :--- | :--- |
| `502` | Model connection / auth | `LLM_BASE_URL` unreachable, bad key, wrong `LLM_AUTH_HEADER` for Azure, Ollama not running or model not pulled. Use Settings → Test connection. |
| `422` | Validation | Generated XML failed XSD validation, ERROR-level graph issues block export, or the capture form has conflicting rows. |
| `415` | File signature | The extension does not match the file contents (e.g. a renamed `.bpm` or `.pdf`). Bizagi `.bpm` files must be exported to `.bpmn` first. |
| `400` | Ingestion / import | Empty file, unsupported format, scanned PDF without a text layer, encrypted document, or a BPMN file with no `<bpmn:process>`. |

---

## Developer Commands

```bash
make test        # pytest + frontend lint
make lint        # TypeScript + design-system lint
make build       # frontend bundle + template assets
make schemas     # fetch official OMG BPMN 2.0 XSD schemas
make templates   # regenerate the capture template files
```

---

## Roadmap (scope v2)

Work is tracked on branch `scope-celonis-v2`.

| Phase | Scope | Status |
| :--- | :--- | :--- |
| 0 | Branch + tag the full-scope build (`v1-full-scope`) | done |
| 1 | Remove sample workflows, Step Builder, and the Signavio/Camunda/ARIS profiles | done |
| 2 | Celonis as default target everywhere; empty start page; two-target toolbar | done |
| 3 | Single Template page with one example process | done |
| 4 | BPMN import from other tools (`/api/import/bpmn`, CLI `import`) | done |
| 5 | Tech-stack slimming and test suite (Vitest + Playwright smoke) | done |
| 6 | Manual import verification: Celonis, bpmn.io, Bizagi, Flowable; round-trips from Camunda/Signavio/ARIS exports | planned |
| 7 | Real-model (Ollama) extraction re-validation and team deployment | planned |
