# Process2BPMN Process Capture Templates

This directory contains standardized, downloadable process capture templates and reference BPMN models designed for Process2BPMN.

---

## 📁 Which File Should You Use?

| File | Format | Recommended For |
|---|---|---|
| **`Process_Capture_Template.xlsx`** | Excel (.xlsx) | **Recommended Default**: Tabular step entry with dropdown roles, auto-formatting, and expandable metadata columns. |
| **`Process_Capture_Template_Example.xlsx`** | Excel (.xlsx) | Reference example showing a complete 8-step employee leave request workflow. |
| **`Process_Capture_Template.docx`** | Word (.docx) | Document-style capture with headings, narrative context, and structured step tables. |
| **`Process_Capture_Template_Example.docx`** | Word (.docx) | Pre-filled Word document showing standard procedure capture. |
| **`default_celonis.bpmn`** | BPMN 2.0 XML | Reference Celonis-compliant template diagram. |

---

## ✍️ How to Fill In the Excel / Word Template

The template uses a simple 8-column primary table (plus 5 optional metadata columns). Every row represents a single workflow element.

### 1. Sequential Steps (`Step ID` & `Step`)
- **Step ID**: Enter a unique sequential integer for each row (`1`, `2`, `3`, etc.).
- **Step**: Enter a clear, action-oriented name (e.g., *Submit Leave Request*, *Verify Documentation*).

### 2. Swimlanes (`Responsible`)
- **Responsible**: The department, role, or actor executing the step (e.g., *Employee*, *Manager*, *HR*, *Finance*, *System*).
- Each distinct Responsible role automatically maps to a visual **Swimlane** in your BPMN diagram.
- Use the **Roles** sheet in the Excel workbook to customize available dropdown choices.

### 3. Step Types (`Type`)
- **`Task`** (Default): Standard user or automated task activity.
- **`Decision`**: Branching gateway that evaluates a condition or rule.
- **`End`**: Terminal event concluding this process branch.

### 4. Branching Logic (`If Yes → Step` & `If No → Step`)
- When **`Type`** is set to `Decision`, specify the target **Step ID** for each outcome:
  - `If Yes → Step`: Next Step ID when approved or condition is true (e.g., `3`).
  - `If No → Step`: Next Step ID when rejected or condition is false (e.g., `8` to reject, or `1` to loop back for revisions).
- For regular `Task` rows, leave these columns empty.

### 5. Concurrent / Parallel Steps (`Parallel Group`)
- To run two or more tasks concurrently across different roles, assign them the **same group identifier** (e.g., `G1`).
- Process2BPMN automatically creates parallel fork (`+`) and join (`+`) gateways synchronizing these tasks.

### 6. Successor Flow (`Next Step`)
- Leave blank to automatically proceed to the next row (`Row N+1`).
- Enter a specific **Step ID** (e.g., `5`) to jump or loop backwards.
- Enter **`END`** to finish the process branch at this step.

### 7. Optional Advanced Columns (Grouped / Collapsible)
- **`Description`**: Detailed work instructions or SOP text.
- **`System/Tool`**: Application used (e.g., *SAP*, *Salesforce*, *Jira*, *Email*).
- **`Input` / `Output`**: Data artifacts, forms, or records consumed or generated.
- **`Duration`**: SLA or estimated completion time (e.g., *10m*, *2h*, *1d*).

---

## 🚀 How to Upload & Generate Diagrams

1. **Web App**: Open the Process2BPMN web application.
2. **Upload**: Drag and drop your saved `.xlsx` or `.docx` file into the upload dropzone.
3. **Instant Diagram**: Process2BPMN will parse your table and immediately render a fully laid-out, standards-compliant BPMN 2.0 diagram.
4. **Export**: Export as `.bpmn`, `.svg`, `.png`, or a complete `.zip` multi-format bundle.
