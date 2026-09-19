# Phase 7 — real-model re-validation and team deployment

Two independent pieces of work. Part A is a correctness question left over from the QA review;
Part B puts the app in front of your team. Do A first — deploying output you have not checked
is how a bad prompt becomes an organisational habit.

---

## Part A — re-validate extraction with a real model

### Why this is necessary

Before the QA review, the extraction prompt never contained the document. `chunker.render_prompt()`
substituted `{{CHUNK_CONTENT}}` while `prompts/extract_chunk.md` used `{{CHUNK_TEXT}}`, so every
real-model conversion extracted from the literal placeholder text. The bug is fixed, but anything
generated before the fix is suspect — including `backend/tests/golden/test_sop_*.bpmn`, which the
test suite now asserts against. If those were produced by the broken prompt, the suite is pinning
nonsense in place.

Structured inputs (the capture template, CSV, imported BPMN) were never affected: they are
converted by rules with no model involved.

### Set up a model

Ollama is the simplest local option:

```
brew install ollama
ollama serve
ollama pull llama3.1:8b
```

Point the app at it in `.env`:

```
LLM_PROVIDER=openai_compatible
LLM_MODEL=llama3.1:8b
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_TIMEOUT=600
```

`LLM_TIMEOUT=600` is not excessive — an 8B model on CPU can take several minutes to emit a 4k-token
JSON document, and the default 90s will cut it off mid-answer.

### Run it

```
cd /Users/gauthamarvind/BPMN-converter && python3 scripts/revalidate_extraction.py
```

This runs the four free-text fixtures through the real model, writes each result to
`revalidation/*.bpmn`, prints a summary and diffs the output against the existing goldens. It
never changes a golden on its own.

One fixture at a time, if a run is slow:

```
cd /Users/gauthamarvind/BPMN-converter && python3 scripts/revalidate_extraction.py --only sample_sop.md
```

### Judge the output

For each result, open `revalidation/<name>.bpmn` in [demo.bpmn.io](https://demo.bpmn.io) and ask:

- Are the **steps** real steps from the document, or invented?
- Are the **lanes** the actual roles named in the text?
- Do the **decisions** have both branches, labelled?
- Does the flow order match the document's order?
- Is anything from the document **missing** entirely?

Compare against `backend/tests/fixtures/README.md`, which describes the expected outcome for each
fixture in detail.

### Refresh the goldens — only after reading the diffs

```
cd /Users/gauthamarvind/BPMN-converter && python3 scripts/revalidate_extraction.py --update-goldens
```

Then re-run the suite and commit:

```
cd /Users/gauthamarvind/BPMN-converter && python3 -m pytest backend/tests/test_golden_templates.py
```

A caveat worth keeping in mind: a language model is not deterministic, so goldens generated from
one are a snapshot of one run, not a specification. If they turn out to churn on every run, the
better answer is to assert on structure (counts, lane names, gateway labels) rather than byte
equality — tell me if that happens and I will rewrite that test.

---

## Part B — deploy for the team

### What the app already provides

`backend/security.py` has the pieces; deployment is a matter of turning them on:

| Setting | Production value | Why |
| :--- | :--- | :--- |
| `APP_AUTH_MODE` | `proxy` | The reverse proxy authenticates; the app trusts a header. `none` means anyone who reaches the port is a user. |
| `ALLOW_CLIENT_LLM_OVERRIDES` | `false` | Otherwise a client can point the server at a model endpoint of its choosing. |
| `LLM_ALLOW_PRIVATE_BASE_URLS` | `false` | Blocks requests to internal addresses and cloud metadata endpoints. |
| `LLM_BASE_URL_ALLOWLIST` | your hosts | The allowlist is the real control; the two flags above are the defaults around it. |
| `EXPOSE_SERVER_CONFIG` | `false` | Keeps the model base URL and key hint out of the public `/api/health`. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per-user limit; a model call is expensive. |
| `MAX_CONCURRENT_EXTRACTIONS` | `4` | Extraction slots; requests beyond this get a 503 rather than dragging the server down. |

### Files in this repo

| File | Purpose |
| :--- | :--- |
| `docker-compose.prod.yml` | Production overlay: hosted-mode settings, loopback binding, health check, log rotation |
| `deploy/nginx.conf` | TLS termination, SSO via `auth_request`, identity header, timeouts sized for model calls |
| `deploy/process2bpmn.service` | systemd unit for hosts not running Docker, with filesystem hardening |

### Docker route

```
cd /opt/process2bpmn && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### systemd route

Follow the header comment in `deploy/process2bpmn.service`.

### Either way

1. Put `deploy/nginx.conf` in place, change the three marked values, `nginx -t`, reload.
2. Get a certificate: `sudo certbot --nginx -d process2bpmn.example.com`.
3. Keep `.env` on the server only, `chmod 640`, owned by root with the service user as group. It
   holds your model API key.
4. Back up `./data` — uploaded reference templates and per-user defaults live there and exist
   nowhere else.

### Verify the deployment

Work through these from a machine that is *not* the server:

- **V1** — `https://your-host/` redirects to your identity provider, and reaches the app after login.
- **V2** — `curl https://your-host/api/profiles` without a session returns 401, not data.
- **V3** — header spoofing fails:
  ```
  curl -H "X-Forwarded-User: someone-else" https://your-host/api/templates
  ```
  Must return 401. If it returns data, nginx is passing the client's header through and every
  identity in the app is forgeable — stop and fix that before anyone uses it.
- **V4** — `curl https://your-host/api/health` works (the proxy needs it) but contains no
  `base_url` or key hint.
- **V5** — a conversion of a large document completes without a 504 (this is what the 300s proxy
  timeouts are for).
- **V6** — two different people each upload a reference template and see only their own in the
  Template manager.
- **V7** — restart the service and confirm uploaded templates survive (the `./data` volume).

Send me anything that fails, V3 especially.
