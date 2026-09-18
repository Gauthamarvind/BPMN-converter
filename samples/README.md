# Process2BPMN Sample Workflows

This directory contains ready-to-convert sample inputs in various formats (.xlsx, .docx, .vtt, .pdf, .md, .txt, .csv) demonstrating how Process2BPMN converts unstructured documents and structured spreadsheets into standard BPMN 2.0 diagrams.

---

## 📋 Available Samples and Expected Diagram Outcomes

### 1. `sample_leave_request.xlsx` (Excel Template)
- **Format**: Microsoft Excel (.xlsx workbook with `Process`, `Roles`, `Example`, and `Instructions` sheets).
- **Description**: Complete 8-step employee leave request and approval process.
- **Expected BPMN Output**:
  - **3 Swimlanes**: `Employee`, `Manager`, `HR`.
  - **1 Start Event** and **2 End Events** (`Leave Approved`, `Leave Rejected`).
  - **1 Exclusive Gateway (XOR)**: Manager approval check with "Approved" branching to Step 4 and "Rejected" branching to Step 8.
  - **1 Parallel Gateway Pair (AND fork/join)**: Group `G1` synchronizing parallel tasks (*Send Calendar Invite* in Employee lane and *Update Payroll Records* in HR lane).

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
- **Description**: Loan underwriting process table with condition branches.
- **Expected BPMN Output**: Loan application review with credit check gateway and underwriting outcomes.

---

## ⚡ How to Run & Test
You can load any sample directly inside the web application via **Toolbar → Templates & samples** or the empty state card, or test via the backend API:

```bash
curl -X POST http://localhost:3000/api/convert \\
  -F "file=@samples/sample_leave_request.xlsx" \\
  -F "mock=true"
```
