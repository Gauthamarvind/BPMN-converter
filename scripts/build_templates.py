#!/usr/bin/env python3
"""
Build script to generate all committed downloadable templates into the top-level templates/ directory.
Outputs:
- Process_Capture_Template.xlsx (blank)
- Process_Capture_Template_Example.xlsx (filled leave-request)
- Process_Capture_Template.docx (blank)
- Process_Capture_Template_Example.docx (filled leave-request)
- default_celonis.bpmn (built-in reference template)
- README.md (plain-language instructions for users)
"""

import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.templates.blank_generator import (
    generate_blank_xlsx,
    generate_blank_docx,
)

TEMPLATES_DIR = PROJECT_ROOT / "templates"
DATA_TEMPLATES_DIR = PROJECT_ROOT / "data" / "templates"

README_CONTENT = """# Process2BPMN Process Capture Templates

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
"""


def build_all_templates() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating Process_Capture_Template.xlsx (blank)...")
    blank_xlsx = generate_blank_xlsx(include_sample=False)
    (TEMPLATES_DIR / "Process_Capture_Template.xlsx").write_bytes(blank_xlsx)

    print("Generating Process_Capture_Template_Example.xlsx (filled leave-request)...")
    example_xlsx = generate_blank_xlsx(include_sample=True)
    (TEMPLATES_DIR / "Process_Capture_Template_Example.xlsx").write_bytes(example_xlsx)

    print("Generating Process_Capture_Template.docx (blank)...")
    blank_docx = generate_blank_docx(include_sample=False)
    (TEMPLATES_DIR / "Process_Capture_Template.docx").write_bytes(blank_docx)

    print("Generating Process_Capture_Template_Example.docx (filled leave-request)...")
    example_docx = generate_blank_docx(include_sample=True)
    (TEMPLATES_DIR / "Process_Capture_Template_Example.docx").write_bytes(example_docx)

    # Copy the built-in reference BPMN template (scope v2: Celonis only)
    vendors = ["celonis"]
    for vendor in vendors:
        vendor_dir = DATA_TEMPLATES_DIR / f"default_{vendor}"
        vendor_bpmn = vendor_dir / f"default_{vendor}.bpmn"
        if vendor_bpmn.exists():
            dest_file = TEMPLATES_DIR / f"default_{vendor}.bpmn"
            print(f"Copying reference template {vendor_bpmn.name} -> {dest_file.name}...")
            shutil.copyfile(vendor_bpmn, dest_file)
        else:
            print(f"Warning: {vendor_bpmn} not found!")

    print("Writing templates/README.md...")
    (TEMPLATES_DIR / "README.md").write_text(README_CONTENT.strip() + "\n", encoding="utf-8")

    print("All templates built successfully in templates/!")


if __name__ == "__main__":
    build_all_templates()
