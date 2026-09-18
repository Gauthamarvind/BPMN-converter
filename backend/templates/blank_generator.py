"""
Blank Template Generator (v2).
Generates downloadable, fully-styled .xlsx workbooks and .docx documents conforming to
the Process2BPMN v2 template specification with openpyxl data validations,
grouped advanced columns, frozen headers, column tooltips, and sample sheets.
"""

from __future__ import annotations
import io
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


PROCESS_HEADERS = [
    "Step ID",
    "Step",
    "Responsible",
    "Type",
    "If Yes → Step",
    "If No → Step",
    "Parallel Group",
    "Next Step",
    "Description",
    "System/Tool",
    "Input",
    "Output",
    "Duration"
]

COLUMN_TOOLTIPS = {
    "Step ID": "Unique sequential integer identifier for this step (e.g. 1, 2, 3).",
    "Step": "Name of the task or decision question (e.g. 'Submit Expense', 'Approved?').",
    "Responsible": "Role or swimlane owner responsible for executing this step.",
    "Type": "Step type: Task, Decision (gateway), or End (termination). Default is Task.",
    "If Yes → Step": "Target Step ID when the decision question is evaluated as Yes / True.",
    "If No → Step": "Target Step ID when the decision question is evaluated as No / False.",
    "Parallel Group": "Group ID (e.g. G1) for concurrent tasks running in parallel.",
    "Next Step": "Successor Step ID, 'END' to finish, or leave blank for consecutive next row.",
    "Description": "Detailed execution instructions and SOP documentation.",
    "System/Tool": "Application or tool used (e.g. SAP, Jira, Concur, Salesforce).",
    "Input": "Input data, document, or prerequisite trigger.",
    "Output": "Output deliverable, updated state, or artifact produced.",
    "Duration": "Estimated completion time or SLA (e.g. '2h', '1d')."
}

DEFAULT_ROLES = [
    "Employee",
    "Manager",
    "HR",
    "Finance",
    "System",
    "Department Head",
    "Approver",
    "Unassigned"
]

INSTRUCTIONS_LINES = [
    "1. Enter process steps sequentially with a Step ID, Step description, and Responsible role.",
    "2. Use the Roles sheet to define or customize available team roles and swimlanes.",
    "3. Set Type to 'Decision' and provide both 'If Yes' and 'If No' target Step IDs for branching.",
    "4. Set matching 'Parallel Group' IDs (e.g., G1) on two or more rows for concurrent flows.",
    "5. Leave 'Next Step' blank for sequential flow, specify a Step ID to jump/loop, or enter 'END'."
]

# 8-row leave-request process containing a decision, a loop back, a parallel group across 2 lanes, and an End
EXAMPLE_ROWS = [
    [
        "1",
        "Submit Leave Request",
        "Employee",
        "Task",
        "",
        "",
        "",
        "2",
        "Employee selects leave dates and submits request in portal",
        "HR Portal",
        "Date range",
        "Leave Application",
        "10m"
    ],
    [
        "2",
        "Check Leave Balance",
        "HR",
        "Decision",
        "3",
        "8",
        "",
        "",
        "HR verifies employee has sufficient accrued PTO balance",
        "HRIS",
        "Leave Application",
        "Balance Check",
        "30m"
    ],
    [
        "3",
        "Manager Approval",
        "Manager",
        "Decision",
        "4",
        "1",
        "",
        "",
        "Manager reviews workload coverage and approves or sends back",
        "Email / HR Portal",
        "Leave Application",
        "Approval Decision",
        "1d"
    ],
    [
        "4",
        "Record in Payroll",
        "Finance",
        "Task",
        "",
        "",
        "G1",
        "6",
        "Payroll adjusts upcoming cycle for approved time-off",
        "Payroll System",
        "Approved Request",
        "Payroll Entry",
        "1h"
    ],
    [
        "5",
        "Update HR Calendar",
        "HR",
        "Task",
        "",
        "",
        "G1",
        "6",
        "HR team publishes employee out-of-office schedule",
        "Shared Calendar",
        "Approved Request",
        "Calendar Block",
        "15m"
    ],
    [
        "6",
        "Send Confirmation Email",
        "System",
        "Task",
        "",
        "",
        "",
        "7",
        "Automated service delivers confirmation to employee & manager",
        "Mail Service",
        "Approval Record",
        "Confirmation Email",
        "Instant"
    ],
    [
        "7",
        "Archival & Close",
        "System",
        "Task",
        "",
        "",
        "",
        "END",
        "Request record is marked completed and archived in database",
        "Document Archive",
        "Completed Case",
        "Audit Log",
        "Instant"
    ],
    [
        "8",
        "Notify Rejection & Close",
        "HR",
        "End",
        "",
        "",
        "",
        "END",
        "HR informs employee of insufficient balance and terminates request",
        "HRIS",
        "Rejection Reason",
        "Rejection Notice",
        "15m"
    ]
]


def generate_blank_xlsx(include_sample: bool = True) -> bytes:
    """
    Generates a structured, fully styled openpyxl workbook conforming to Item C1.
    Sheets: 'Process', 'Roles', 'Example', 'Instructions', and hidden '_meta'.
    """
    wb = openpyxl.Workbook()

    # Style definitions
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    adv_header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    adv_header_font = Font(name="Segoe UI", size=10, bold=True, color="E2E8F0")

    decision_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    disabled_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=10)
    title_font = Font(name="Segoe UI", size=11, bold=True, color="0F172A")
    label_font = Font(name="Segoe UI", size=10, bold=True, color="475569")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # 1. Sheet: "Process"
    ws_process = wb.active
    ws_process.title = "Process"

    # Title block
    ws_process["A1"] = "Process Name:"
    ws_process["A1"].font = label_font
    ws_process["B1"] = "Employee Leave Request" if include_sample else "New Business Process"
    ws_process["B1"].font = title_font
    ws_process.row_dimensions[1].height = 24

    # Table Header Row (Row 3)
    header_row_idx = 3
    for col_idx, header_name in enumerate(PROCESS_HEADERS, start=1):
        cell = ws_process.cell(row=header_row_idx, column=col_idx, value=header_name)
        cell.fill = adv_header_fill if col_idx > 8 else header_fill
        cell.font = adv_header_font if col_idx > 8 else header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

        # Tooltip comment
        if header_name in COLUMN_TOOLTIPS:
            comment = Comment(COLUMN_TOOLTIPS[header_name], "Process2BPMN")
            comment.width = 250
            comment.height = 60
            cell.comment = comment

    ws_process.row_dimensions[header_row_idx].height = 28
    ws_process.freeze_panes = f"A{header_row_idx + 1}"

    # Populate rows if sample or add empty rows
    rows_to_insert = EXAMPLE_ROWS if include_sample else [
        ["1", "", "Employee", "Task", "", "", "", "2", "", "", "", "", ""],
        ["2", "", "Manager", "Task", "", "", "", "3", "", "", "", "", ""],
        ["3", "", "HR", "End", "", "", "", "END", "", "", "", "", ""]
    ]

    for r_offset, row_data in enumerate(rows_to_insert, start=1):
        curr_row = header_row_idx + r_offset
        is_decision = len(row_data) > 3 and row_data[3] == "Decision"

        for c_idx, val in enumerate(row_data, start=1):
            c = ws_process.cell(row=curr_row, column=c_idx, value=val)
            c.font = regular_font
            c.border = thin_border

            # Alignment
            if c_idx in (1, 4, 5, 6, 7, 8, 13):
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

            # Decision tinting and Yes/No graying
            if is_decision:
                c.fill = decision_fill
            elif c_idx in (5, 6):
                c.fill = disabled_fill

        ws_process.row_dimensions[curr_row].height = 22

    # Group and collapse advanced columns (I to M: cols 9 to 13)
    ws_process.column_dimensions.group('I', 'M', hidden=True)

    # Column widths
    col_widths = [10, 28, 18, 14, 15, 15, 15, 14, 30, 18, 18, 18, 12]
    for idx, width in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws_process.column_dimensions[col_letter].width = width

    # Data Validations: Responsible dropdown & Type dropdown
    role_dv = DataValidation(type="list", formula1="Roles!$A$2:$A$50", allow_blank=True)
    role_dv.error = "Please select a valid role from the Roles sheet."
    role_dv.errorTitle = "Invalid Role"
    role_dv.prompt = "Select role from dropdown"
    ws_process.add_data_validation(role_dv)
    role_dv.add(f"C4:C100")

    type_dv = DataValidation(type="list", formula1='"Task,Decision,End"', allow_blank=False)
    type_dv.error = "Type must be Task, Decision, or End."
    type_dv.errorTitle = "Invalid Step Type"
    ws_process.add_data_validation(type_dv)
    type_dv.add(f"D4:D100")

    # 2. Sheet: "Roles"
    ws_roles = wb.create_sheet(title="Roles")
    ws_roles["A1"] = "Role Name"
    ws_roles["A1"].font = header_font
    ws_roles["A1"].fill = header_fill
    ws_roles["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_roles.row_dimensions[1].height = 26

    for r_idx, role_name in enumerate(DEFAULT_ROLES, start=2):
        c = ws_roles.cell(row=r_idx, column=1, value=role_name)
        c.font = regular_font
        c.border = thin_border
        ws_roles.row_dimensions[r_idx].height = 20
    ws_roles.column_dimensions["A"].width = 25

    # 3. Sheet: "Example"
    ws_example = wb.create_sheet(title="Example")
    ws_example["A1"] = "Process Name:"
    ws_example["A1"].font = label_font
    ws_example["B1"] = "Employee Leave Request Example"
    ws_example["B1"].font = title_font

    for c_idx, h in enumerate(PROCESS_HEADERS, start=1):
        c = ws_example.cell(row=header_row_idx, column=c_idx, value=h)
        c.fill = adv_header_fill if c_idx > 8 else header_fill
        c.font = adv_header_font if c_idx > 8 else header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border
    ws_example.row_dimensions[header_row_idx].height = 28
    ws_example.freeze_panes = f"A{header_row_idx + 1}"

    for r_offset, row_data in enumerate(EXAMPLE_ROWS, start=1):
        curr_row = header_row_idx + r_offset
        is_decision = row_data[3] == "Decision"
        for c_idx, val in enumerate(row_data, start=1):
            c = ws_example.cell(row=curr_row, column=c_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            if c_idx in (1, 4, 5, 6, 7, 8, 13):
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")
            if is_decision:
                c.fill = decision_fill
            elif c_idx in (5, 6):
                c.fill = disabled_fill
        ws_example.row_dimensions[curr_row].height = 22

    for idx, width in enumerate(col_widths, start=1):
        ws_example.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    ws_example.column_dimensions.group('I', 'M', hidden=True)

    # 4. Sheet: "Instructions" (maximum 5 lines)
    ws_instr = wb.create_sheet(title="Instructions")
    ws_instr["A1"] = "How to Fill Out this Process Template"
    ws_instr["A1"].font = Font(name="Segoe UI", size=12, bold=True, color="1E293B")
    ws_instr.row_dimensions[1].height = 26

    for idx, line in enumerate(INSTRUCTIONS_LINES, start=2):
        c = ws_instr.cell(row=idx, column=1, value=line)
        c.font = regular_font
        ws_instr.row_dimensions[idx].height = 22
    ws_instr.column_dimensions["A"].width = 90

    # 5. Hidden Sheet: "_meta"
    ws_meta = wb.create_sheet(title="_meta")
    ws_meta.sheet_state = "hidden"
    ws_meta["A1"] = "template_version"
    ws_meta["B1"] = "2"
    ws_meta["A2"] = "column_map"
    ws_meta["B2"] = json.dumps({
        "step_id": 1,
        "step": 2,
        "responsible": 3,
        "type": 4,
        "if_yes": 5,
        "if_no": 6,
        "parallel_group": 7,
        "next_step": 8,
        "description": 9,
        "system": 10,
        "input": 11,
        "output": 12,
        "duration": 13
    })

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def generate_blank_docx(include_sample: bool = True) -> bytes:
    """
    Generates a structured Word document capture table conforming to the v2 specification.
    """
    doc = docx.Document()

    # Title
    title = doc.add_heading("Standard Process Capture Template", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    doc.add_paragraph("Process Name: " + ("Employee Leave Request" if include_sample else "[Enter Process Name Here]"))

    desc = doc.add_paragraph(
        "Fill out sequential process steps below. Each row corresponds to a Task, Decision, or End step."
    )
    desc.paragraph_format.space_after = Pt(12)

    rows_data = EXAMPLE_ROWS if include_sample else [
        ["1", "Submit Request", "Employee", "Task", "", "", "", "2", "", "", "", "", ""],
        ["2", "Review Request", "Manager", "Task", "", "", "", "3", "", "", "", "", ""],
        ["3", "Close Request", "HR", "End", "", "", "", "END", "", "", "", "", ""]
    ]

    cols_count = len(PROCESS_HEADERS)
    rows_count = len(rows_data) + 1
    table = doc.add_table(rows=rows_count, cols=cols_count)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # Header Row
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(PROCESS_HEADERS):
        hdr_cells[i].text = h
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.bold = True
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(30, 41, 59)

    # Data Rows
    for r_idx, row_vals in enumerate(rows_data):
        row_cells = table.rows[r_idx + 1].cells
        for c_idx, val in enumerate(row_vals):
            row_cells[c_idx].text = str(val) if val is not None else ""
            p = row_cells[c_idx].paragraphs[0]
            if c_idx in (0, 3, 4, 5, 6, 7):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.size = Pt(8.5)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def build_xlsx_from_steps(process_name: str, steps: List[Dict[str, Any]], roles: Optional[List[str]] = None) -> bytes:
    """
    Builds an identical .xlsx workbook given a JSON list of steps from the Step Builder sheet.
    """
    row_data_list = []
    for s in steps:
        row_data_list.append([
            str(s.get("step_id", "")),
            str(s.get("step", "")),
            str(s.get("responsible", "Unassigned")),
            str(s.get("type", "Task")),
            str(s.get("if_yes", "") or ""),
            str(s.get("if_no", "") or ""),
            str(s.get("parallel_group", "") or ""),
            str(s.get("next_step", "") or ""),
            str(s.get("description", "") or ""),
            str(s.get("system", "") or ""),
            str(s.get("input_data", "") or ""),
            str(s.get("output_data", "") or ""),
            str(s.get("duration", "") or "")
        ])

    wb = openpyxl.Workbook()
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    adv_header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    adv_header_font = Font(name="Segoe UI", size=10, bold=True, color="E2E8F0")

    decision_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    disabled_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=10)
    title_font = Font(name="Segoe UI", size=11, bold=True, color="0F172A")
    label_font = Font(name="Segoe UI", size=10, bold=True, color="475569")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    ws_process = wb.active
    ws_process.title = "Process"
    ws_process["A1"] = "Process Name:"
    ws_process["A1"].font = label_font
    ws_process["B1"] = process_name or "Custom Process"
    ws_process["B1"].font = title_font

    header_row_idx = 3
    for col_idx, header_name in enumerate(PROCESS_HEADERS, start=1):
        cell = ws_process.cell(row=header_row_idx, column=col_idx, value=header_name)
        cell.fill = adv_header_fill if col_idx > 8 else header_fill
        cell.font = adv_header_font if col_idx > 8 else header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    ws_process.freeze_panes = f"A{header_row_idx + 1}"

    for r_offset, row_data in enumerate(row_data_list, start=1):
        curr_row = header_row_idx + r_offset
        is_decision = len(row_data) > 3 and row_data[3] == "Decision"
        for c_idx, val in enumerate(row_data, start=1):
            c = ws_process.cell(row=curr_row, column=c_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            if c_idx in (1, 4, 5, 6, 7, 8, 13):
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")
            if is_decision:
                c.fill = decision_fill
            elif c_idx in (5, 6):
                c.fill = disabled_fill

    ws_process.column_dimensions.group('I', 'M', hidden=True)

    # Roles Sheet
    ws_roles = wb.create_sheet(title="Roles")
    ws_roles["A1"] = "Role Name"
    ws_roles["A1"].font = header_font
    ws_roles["A1"].fill = header_fill
    active_roles = roles or DEFAULT_ROLES
    for r_idx, role_name in enumerate(active_roles, start=2):
        c = ws_roles.cell(row=r_idx, column=1, value=role_name)
        c.font = regular_font
        c.border = thin_border

    # Instructions Sheet
    ws_instr = wb.create_sheet(title="Instructions")
    ws_instr["A1"] = "How to Fill Out this Process Template"
    ws_instr["A1"].font = Font(name="Segoe UI", size=12, bold=True, color="1E293B")
    for idx, line in enumerate(INSTRUCTIONS_LINES, start=2):
        c = ws_instr.cell(row=idx, column=1, value=line)
        c.font = regular_font

    # Hidden _meta
    ws_meta = wb.create_sheet(title="_meta")
    ws_meta.sheet_state = "hidden"
    ws_meta["A1"] = "template_version"
    ws_meta["B1"] = "2"

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
