"""
Blank Template Generator.
Generates blank downloadable .xlsx and .docx document templates conforming to template.yaml.
"""

from __future__ import annotations
import io
from pathlib import Path
from typing import Tuple


BLANK_HEADERS = [
    "Step #",
    "Activity",
    "Role",
    "Task Type",
    "Decision?",
    "Condition",
    "Next Steps",
    "System",
    "Input",
    "Output",
    "Notes"
]

SAMPLE_ROWS = [
    [
        "1",
        "Submit Expense Report",
        "Employee",
        "User",
        "No",
        "",
        "2",
        "Concur / SAP",
        "Receipts",
        "Expense Claim",
        "Employee fills form and attaches itemized receipts"
    ],
    [
        "2",
        "Review and Validate Claim",
        "Manager",
        "User",
        "Yes",
        "",
        "3, 4",
        "Approval Portal",
        "Expense Claim",
        "Validation Status",
        "Manager checks policy compliance and budget"
    ],
    [
        "3",
        "Process Reimbursement Payment",
        "Finance",
        "Automated",
        "No",
        "Claim Approved == true",
        "5",
        "Core Banking",
        "Approved Claim",
        "Remittance Advice",
        "Finance triggers direct EFT transfer"
    ],
    [
        "4",
        "Reject and Notify Employee",
        "Manager",
        "User",
        "No",
        "Claim Approved == false",
        "5",
        "Email / Concur",
        "Rejection Reason",
        "Notification",
        "Manager logs rejection comments"
    ],
    [
        "5",
        "Archive Records",
        "System",
        "Automated",
        "No",
        "",
        "End",
        "Document Archive",
        "Claim Records",
        "Audit Log",
        "Process completed and records retained"
    ]
]


def generate_blank_xlsx(include_sample: bool = True) -> bytes:
    """Generates a downloadable .xlsx file with formatting and validation tips."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Process Steps"

    # Header style
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    ws.append(BLANK_HEADERS)
    for col_num in range(1, len(BLANK_HEADERS) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    if include_sample:
        data_font = Font(name="Segoe UI", size=10)
        for row_data in SAMPLE_ROWS:
            ws.append(row_data)
            row_idx = ws.max_row
            for col_num in range(1, len(row_data) + 1):
                c = ws.cell(row=row_idx, column=col_num)
                c.font = data_font
                c.border = thin_border
                if col_num in (1, 4, 5, 7):
                    c.alignment = Alignment(horizontal="center", vertical="center")

    # Column widths
    col_widths = [10, 30, 18, 14, 12, 25, 14, 20, 18, 18, 40]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    ws.row_dimensions[1].height = 28

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def generate_blank_docx(include_sample: bool = True) -> bytes:
    """Generates a downloadable .docx file with a styled process capture table."""
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = docx.Document()

    # Title
    title = doc.add_heading("Standard Process Capture Template", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    desc = doc.add_paragraph(
        "Fill out the table below with sequential process steps. "
        "Each row represents an activity or gateway, assigned to a specific role/swimlane."
    )
    desc.paragraph_format.space_after = Pt(12)

    rows_count = len(SAMPLE_ROWS) + 1 if include_sample else 6
    cols_count = len(BLANK_HEADERS)
    table = doc.add_table(rows=rows_count, cols=cols_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # Header Row
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(BLANK_HEADERS):
        hdr_cells[i].text = h
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.bold = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(30, 41, 59)

    # Sample or blank rows
    if include_sample:
        for r_idx, row_data in enumerate(SAMPLE_ROWS):
            row_cells = table.rows[r_idx + 1].cells
            for c_idx, val in enumerate(row_data):
                row_cells[c_idx].text = val
                p = row_cells[c_idx].paragraphs[0]
                for run in p.runs:
                    run.font.size = Pt(9)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
