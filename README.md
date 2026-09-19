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

## How the app works

The page opens empty — nothing is preloaded and no model is called until you convert something.

### A. Convert a document or pasted text
1. Drop a file on the canvas or into the left sidebar, or paste text.
2. The target tool is **Celonis** by default. Switch to **Generic BPMN 2.0** in the toolbar if you need a plain OMG file.
3. Click **Convert**.
4. Review the diagram; click any element to see its details and the source sentence it came from. The **Issues** tab lists warnings and anything that blocks export.
5. **Export** as `.bpmn`, `.svg`, `.png`, or a ZIP containing both the Celonis and generic `.bpmn` files.

### B. Import a BPMN file from another tool
1. Click **Import BPMN** (sidebar or empty state) and choose a `.bpmn` / `.xml` exported from Camunda, Signavio, ARIS, Bizagi, Flowable or bpmn.io.
2. The importer detects the source tool, removes vendor extensions, validates the graph and shows the diagram. Anything it had to drop or repair is listed under **Issues**.
3. Export as Celonis or generic BPMN 2.0 exactly as in flow A.

How to get a BPMN 2.0 file out of each tool:

| Source tool | Export action | Notes |
| :--- | :--- | :--- |
| Camunda Modeler 7/8 | File → Save As → `.bpmn` | Camunda namespace and `zeebe:` extensions are stripped. |
| SAP Signavio | Export → BPMN 2.0 XML | `sid-*` IDs are kept; Signavio styling tags are dropped. |
| Software AG ARIS | Export → BPMN 2.0 | ARIS attribute extensions are dropped. |
| Bizagi Modeler | Export/Import → Export to BPMN | Bizagi's native `.bpm` is not BPMN — export to `.bpmn` first. |
| Flowable | Export → BPMN 2.0 XML | `flowable:` extensions are dropped. |
| bpmn.io / other | Download `.bpmn` | Imported as-is. |

### C. Use the process capture template (no model needed)
1. Open **Template** in the toolbar. One page shows the capture form and one filled-in example process.
2. Download the blank Excel (or Word) form, fill it in, and upload it like any other file.
3. The rows are converted by rules and any row problems are reported with the row number.

### D. Reuse your own reference diagram
1. **Templates → Upload** a `.bpmn` reference diagram from Celonis or a generic tool.
2. Select it in the toolbar and, if needed, open **Lane mapping** to match your roles to its lanes.
3. Convert or re-render; the export uses the template's pools, lanes and namespaces.

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

## Command Line

```bash
# Convert a document (Celonis is the default target)
python3 -m backend.cli convert path/to/sop.docx -o converted/sop.bpmn

# Generic BPMN 2.0 instead
python3 -m backend.cli convert path/to/sop.docx -p generic -o converted/sop_generic.bpmn

# Import a BPMN file from another tool and re-export for Celonis
python3 -m backend.cli import path/to/camunda_export.bpmn -o converted/for_celonis.bpmn

# Offline rule engine (no model)
python3 -m backend.cli convert path/to/sop.md --mock -o converted/sop.bpmn

# List export targets
python3 -m backend.cli profiles
```

`convert` and `import` exit with code `2` when the diagram has ERROR-level issues; add `--force` to write the file anyway for inspection.

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
| 2 | Celonis as default target everywhere; empty start page; two-target toolbar | planned |
| 3 | Single Template page with one example process | done |
| 4 | BPMN import from other tools (`/api/import/bpmn`, CLI `import`) | planned |
| 5 | Tech-stack slimming and test suite (Vitest + Playwright smoke) | planned |
| 6 | Manual import verification: Celonis, bpmn.io, Bizagi, Flowable; round-trips from Camunda/Signavio/ARIS exports | planned |
| 7 | Real-model (Ollama) extraction re-validation and team deployment | planned |
