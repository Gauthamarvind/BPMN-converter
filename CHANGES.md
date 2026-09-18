# QA review fixes — Process2BPMN

Applies the findings from the requirements/functional review. Every item below maps to a
test in `backend/tests/test_review_fixes.py` or `backend/tests/test_frontend_api_contract.py`.

## Before you push (required)

1. Install and run the suite (the fixes were authored offline; API-level tests are unexecuted):
   ```bash
   pip install -r backend/requirements.txt      # adds defusedxml
   pytest -v
   npm install && npm run lint && npm run build
   ```
2. Regenerate the golden files — the layout fix changes coordinates for the loop case:
   ```bash
   python -m backend.tests.test_golden_templates --update
   ```
   Open the four `backend/tests/golden/*.bpmn` files in bpmn.io and check the loop target
   (`decision_with_loop`) now sits left of the gateway. Commit the regenerated files.
3. Commit a `package-lock.json` (`npm install` creates it) so CI can go back to `npm ci`.

## Fixed in this change set

### Correctness — core requirement (text → BPMN)
- **The LLM never received the document.** `prompts/extract_chunk.md` uses `{{CHUNK_TEXT}}` /
  `{{POOLS_HINT}}`; the chunker substituted `{{CHUNK_CONTENT}}`. Every real-model conversion was
  extracting from the literal placeholder. Fixed in `chunker.render_prompt()`, which now
  substitutes both spellings and raises if the text does not land in the prompt.
- Long-document merge fallback (`_deterministic_union`) dropped elements with colliding ids and
  kept a start/end per chunk. Now namespaces each fragment, unifies lanes by name, keeps one
  start and one end, and stitches chunks in order.
- Lane mapper called `provider.generate()`, which no adapter implements → LLM lane mapping
  silently returned nothing. Now uses `provider.complete()`.
- `provider=mock` emitted `sourceRef/targetRef` (loader reads `sourceId/targetId`) so every
  flow was dropped. Mock adapter is now a thin wrapper over the single rule engine, and the
  pipeline treats `provider=mock` exactly like `mock=true`.

### Layout
- Loop-backs (`Rejected → back to Draft`) inverted node order. New `graph_utils.py`: DFS cycle
  breaking from the start events, longest-path layering, barycenter crossing reduction. Loop
  edges are routed underneath, staggered, and the lane grows to keep them inside.

### Validation / export gate
- Validator warns on implicit splits (task with 2+ outgoing flows) and unbalanced parallel
  gateways; docstring now describes what it does.
- `strict=true` on `/api/convert`, `/api/convert-json`, `/api/render` → 422 `ExportBlockedError`
  instead of returning an unreviewed diagram. `/api/export/bpmn` and `/api/export/bulk` always
  refuse blocked processes and XSD-validate every file. CLI exits 2 unless `--force`.
- Bulk ZIP previously contained the same XML five times under vendor names (client-side
  fallback). The UI now calls the server, which serializes one file per profile.

### Multi-user hardening (`backend/security.py`, `backend/identity.py`)
- `APP_AUTH_MODE=none|proxy|token`; `/api/*` returns 401 without identity (health stays public).
- Templates: `TemplateStorage.delete_template("..")` would `rmtree` the `data/` folder — ids are
  now validated and path-checked. Uploaded templates carry `owner_id`; built-ins cannot be
  deleted; "default" is stored per user.
- `/api/convert` was `async def` calling the synchronous pipeline → one slow model call froze the
  server for everyone. Now `run_in_threadpool` + `MAX_CONCURRENT_EXTRACTIONS` slots (503 when
  full) + `RATE_LIMIT_PER_MINUTE`.
- Client-supplied `base_url` validated (no private/loopback/metadata hosts when hosted,
  optional allowlist). `ALLOW_CLIENT_LLM_OVERRIDES=false` forces the server key for everyone.
- `/api/health` no longer exposes the key hint / base URL on shared deployments.
- CORS from `CORS_ALLOW_ORIGINS`; the invalid `*` + credentials combination is gone.
- SPA fallback can no longer serve files outside `dist/`.
- Template XML: any DOCTYPE/ENTITY rejected; parsed with `defusedxml`.

### Template management
- `TemplateStorage.save_template()` did not exist and the UI posted to a route that did not
  exist. Added `POST /api/templates` (accepts `name`), `GET /api/templates/{id}/download`,
  `save_template()`; `/api/templates/upload` kept as alias.

### Table / Step Builder parser
- One rule-based header mapper replaces three copy-pasted substring matchers (`Notes` no longer
  maps to `If No`, `Input` never matches `Output`).
- Decision or End rows with a `Next Step` are reported (were silently ignored).
- Parallel-group members on non-consecutive rows are rejected (they bypassed the fork).

### Frontend
- Open questions were read from `open_questions: string[]`; the server sends
  `openQuestions: {topic, question}[]` — they now render with topic + suggested assumption.
- Issues badge counts errors/warnings/lint/row errors/questions; INFO auto-repairs are shown in
  their own collapsible section instead of inflating the count.
- `/api/render` calls are cancellable (fast profile switching no longer races).
- Export failures/successes show toasts; `alert()` removed from the Step Builder, which now
  stays open with the row errors when conversion fails.
- Delete button hidden for built-in templates; Settings explains when overrides are ignored.

### Misc
- CLI `profiles` command crashed with `NameError` (missing import).
- CI no longer hard-fails on the missing `package-lock.json`.
- README: layout claims made accurate; new "Deploying for a team" and "Export gate" sections.
- `.env.example`: multi-user settings documented.

## Known leftovers (not changed here)
- `bun.lock` is stale: it lists `express` and `@google/genai`, which `package.json` does not
  declare. Regenerate or delete it once `package-lock.json` is committed.
- `aris` and `generic` profiles differ only in `maxLabelLength`, so their exports can be
  byte-identical for short labels. If ARIS needs specific namespaces/attributes, add them to
  `profiles/aris.yaml`.
- Real-tool import verification (Camunda Modeler, Signavio, ARIS, Celonis) is still manual —
  see the checklist in the review (T18).
- No Vitest/Playwright suite yet; the Python contract test covers route drift, not UI behaviour.
