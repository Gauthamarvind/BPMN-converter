# Process2BPMN Sample Workflows

This directory contains ready-to-convert sample inputs in various formats (.xlsx, .docx, .vtt, .pdf, .md, .txt, .csv) demonstrating how Process2BPMN converts unstructured documents and structured spreadsheets into standard BPMN 2.0 diagrams.

---

## Which mode produces which result

- **Structured inputs** (`sample_leave_request.xlsx`, `sample_sop.docx`, `sample_process_steps.csv`) are converted **deterministically** — no model is called, and the outcome described below is exact in every mode, including mock mode.
- **Free-text inputs** (`.md`, `.txt`, `.vtt`, `.pdf`) need an LLM (`LLM_PROVIDER` other than `mock`) to reach the outcomes described below. In **mock mode** they still convert, but through a simple rule engine that guesses steps and roles from sentence structure; expect rough names and odd lanes. Mock mode exists to test the pipeline and the importers, not to judge extraction quality.

## 📋 Available Samples and Expected Diagram Outcomes

### 1. `sample_leave_request.xlsx` (Excel Template)
- **Format**: Microsoft Excel (.xlsx workbook with `Process`, `Roles`, `Example`, `Instructions` and hidden `_meta` sheets).
- **Description**: Employee leave request and approval process captured in the fill-in template.
- **Expected BPMN Output** (deterministic, identical in every mode):
  - **5 Swimlanes**: `Employee`, `HR`, `Manager`, `Finance`, `System`.
  - **1 Start Event** and **2 End Events** (`Notify Rejection & Close`, `End`).
  - **2 Exclusive Gateways (XOR)**: `Check Leave Balance` and `Manager Approval`, each with `Yes` / `No` branches; the `No` branch of `Manager Approval` loops back to `Submit Leave Request` (reported once as a loop to confirm).
  - **1 Parallel Gateway Pair (AND split/join)**: group `G1` running `Record in Payroll` (Finance) and `Update HR Calendar` (HR) simultaneously.
  - Every element carries a source reference to its sheet row (visible in the inspector's Source tab).

---

### 2. `sample_sop.docx` (Word Document SOP)
- **Format**: Microsoft Word (.docx with formatted headings, narrative text, and a structured steps table).
- **Description**: Vendor onboarding and compliance verification workflow.
- **Expected BPMN Output**:
  - **4 Swimlanes**: `Procurement`, `Compliance`, `Security`, `Finance`.
  - **Tasks**: *Submit Vendor Application*, *Conduct Risk Assessment*, *Setup Vendor in ERP System*, *Send Welcome Confirmation*.
  - **1 Decision Gateway**: Compliance & Tax ID check leading to risk assessment or rejection notification.

---

### 3. `sample_transcript.vtt` (WebVTT Transcript)
- **Format**: WebVTT caption file (`.vtt`) containing timestamped dialogue cues with `<v Speaker>` voice tags.
- **Description**: Incident escalation interview between an Interviewer and a Support Lead.
- **Expected BPMN Output**:
  - **Lanes**: `Customer Support Agent`, `Incident Manager`, `On-Call Engineering`, `DevOps`.
  - **Gateway**: Severity check branching into Sev-1 Critical bridge war-room response vs. Tier 2 queue.
  - **Flow**: Linear escalation through hotfix development, deployment, and customer notification.

---

### 4. `sample_sop.pdf` (PDF SOP)
- **Format**: Adobe PDF (.pdf) with standard operating procedure paragraphs and numbered steps.
- **Description**: Invoice payment, 3-way matching, and budget audit procedure.
- **Expected BPMN Output**:
  - **Lanes**: `Accounts Payable`, `Finance Director`, `Treasury`, `Finance Specialist`.
  - **Gateway**: Budget threshold decision evaluating whether invoice > $10,000 for executive review.
  - **Disbursement & Closure**: Automated wire transfer and payment record archiving.

---

### 5. `sample_sop.md` (Markdown SOP)
- **Format**: CommonMark markdown (`.md`) with section headers and bullet points.
- **Description**: Procurement requisition, quote comparison, and purchase order workflow.
- **Expected BPMN Output**: Standard procurement flow from department request to purchase order generation.

---

### 6. `sample_interview_transcript.txt` (Text Interview)
- **Format**: Plain text transcript (`.txt`).
- **Description**: Dialogue-driven customer support intake, classification, and resolution discussion.
- **Expected BPMN Output**: Customer support process with intake, triage, and resolution steps.

---

### 7. `sample_process_steps.csv` (Spreadsheet Table)
- **Format**: Comma-separated values (`.csv`).
- **Description**: Order-to-cash step list in the legacy column layout (`Step ID`, `Actor / Role`, `Activity Name`, `Next Step`, `Condition / Rule`, `System`). Multiple targets in `Next Step` (`STEP_04 / STEP_05`) become a decision; the condition on each target row labels its branch.
- **Expected BPMN Output** (deterministic): 7 swimlanes (Customer, Sales Representative, System, Warehouse Operator, Procurement Officer, Logistics Coordinator, Finance Specialist), one exclusive gateway after `Check Inventory Availability` with branches `Stock Available` and `Out of Stock`, a restock loop back into picking, and a single end event.

---

## ⚡ How to Run & Test
You can load any sample directly inside the web application via **Toolbar → Templates & samples** or the empty state card, or test via the backend API:

```bash
curl -X POST http://localhost:3000/api/convert \\
  -F "file=@samples/sample_leave_request.xlsx" \\
  -F "mock=true"
```
