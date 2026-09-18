"""
Structured Document Template Parser.
Extracts rows from .xlsx, .csv, .docx, and .json files and maps them directly
to ProcessIR using a template.yaml configuration or auto-detected headers.
Enforces security: macro-free openpyxl execution, file size limits.
"""

from __future__ import annotations
import re
import csv
import json
import io
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import yaml

from backend.ir.models import (
    ProcessIR,
    FlowNode,
    SequenceFlow,
    Pool,
    Lane,
    SourceRef,
    OpenQuestion,
    DataObject
)
from backend.templates.models import DocumentTemplateConfig, ColumnMapping

MAX_DOC_FILE_SIZE = 25 * 1024 * 1024  # 25MB


DEFAULT_TEMPLATE_YAML = """
version: "1.0"
template_name: "Standard Process Inventory Form"
template_type: "document"
description: "Standard corporate process inventory worksheet"

parsing_rules:
  header_row: 1
  data_start_row: 2
  comment_prefix: "#"

columns:
  step_id:
    aliases: ["Step", "Step #", "ID", "Step ID", "No.", "Index"]
    required: true
    type: "string"

  activity_name:
    aliases: ["Activity", "Step Description", "Task Name", "Process Step", "Action", "Description"]
    required: true
    type: "string"

  role_actor:
    aliases: ["Role", "Actor", "Lane", "Department", "Performer", "Responsible", "Owner"]
    required: false
    default: "General"
    type: "string"

  element_type:
    aliases: ["Task Type", "Type", "BPMN Type", "Element Type"]
    required: false
    default: "task"
    mapping:
      "Manual": "manualTask"
      "User": "userTask"
      "Automated": "serviceTask"
      "System": "serviceTask"
      "Decision": "exclusiveGateway"
      "Gateway": "exclusiveGateway"

  is_decision:
    aliases: ["Decision?", "Is Gateway", "Split?", "Gateway?"]
    required: false
    type: "boolean"

  condition:
    aliases: ["Condition", "Rule", "Branch Condition", "Guard"]
    required: false
    type: "string"

  next_steps:
    aliases: ["Next Step(s)", "Next Steps", "Proceed To", "Target Steps", "Follows", "Next"]
    required: false
    delimiter: ","
    type: "list"

  system:
    aliases: ["System", "Application", "Tool"]
    required: false
    type: "string"

  input_data:
    aliases: ["Input", "Data Input", "Prerequisites"]
    required: false
    type: "string"

  output_data:
    aliases: ["Output", "Deliverable", "Artifact"]
    required: false
    type: "string"

  documentation:
    aliases: ["Notes", "Details", "SOP Reference", "Comments"]
    required: false
    type: "string"

gap_filling:
  auto_connect_sequential: true
  llm_fill_missing_decisions: true
  flag_inferred_fields: true
"""


def load_template_config(yaml_content: Optional[str] = None) -> DocumentTemplateConfig:
    raw = yaml.safe_load(yaml_content or DEFAULT_TEMPLATE_YAML)
    cols: Dict[str, ColumnMapping] = {}
    for col_name, c_data in raw.get("columns", {}).items():
        cols[col_name] = ColumnMapping(
            aliases=c_data.get("aliases", []),
            required=bool(c_data.get("required", False)),
            default=c_data.get("default"),
            type=c_data.get("type", "string"),
            mapping=c_data.get("mapping"),
            delimiter=c_data.get("delimiter")
        )
    return DocumentTemplateConfig(
        version=raw.get("version", "1.0"),
        template_name=raw.get("template_name", "Standard Template"),
        template_type=raw.get("template_type", "document"),
        description=raw.get("description", ""),
        sheet_name=raw.get("parsing_rules", {}).get("sheet_name"),
        header_row=raw.get("parsing_rules", {}).get("header_row", 1),
        data_start_row=raw.get("parsing_rules", {}).get("data_start_row", 2),
        comment_prefix=raw.get("parsing_rules", {}).get("comment_prefix", "#"),
        columns=cols
    )


class DocTemplateParser:
    """
    Parses structured files (.xlsx, .csv, .docx, .json) into ProcessIR deterministically.
    """

    def __init__(self, config: Optional[DocumentTemplateConfig] = None):
        self.config = config or load_template_config()

    def parse_bytes(self, raw_bytes: bytes, filename: str) -> ProcessIR:
        if len(raw_bytes) > MAX_DOC_FILE_SIZE:
            raise ValueError(f"File exceeds maximum allowed size of {MAX_DOC_FILE_SIZE // (1024 * 1024)}MB")

        ext = Path(filename).suffix.lower()
        if ext == ".csv":
            content = raw_bytes.decode("utf-8-sig", errors="replace")
            reader = csv.reader(io.StringIO(content))
            all_lines = [r for r in reader if any(cell.strip() for cell in r)]
            if not all_lines:
                rows = []
            else:
                headers = [h.strip() for h in all_lines[self.config.header_row - 1]]
                data_rows = all_lines[self.config.data_start_row - 1:]
                rows = []
                for r in data_rows:
                    row_dict = {}
                    for i, h in enumerate(headers):
                        if i < len(r):
                            row_dict[h] = r[i].strip()
                    if any(row_dict.values()):
                        rows.append(row_dict)
        elif ext == ".json":
            data = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = data.get("steps", data.get("tasks", data.get("activities", [])))
            else:
                rows = []
        elif ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True, read_only=True)
            sheet = wb[self.config.sheet_name] if self.config.sheet_name and self.config.sheet_name in wb.sheetnames else wb.active
            rows = []
            all_rows = list(sheet.iter_rows(values_only=True))
            if all_rows and len(all_rows) >= self.config.header_row:
                headers = [str(c).strip() if c is not None else "" for c in all_rows[self.config.header_row - 1]]
                for r in all_rows[self.config.data_start_row - 1:]:
                    row_dict = {}
                    for i, h in enumerate(headers):
                        if i < len(r) and h:
                            val = r[i]
                            row_dict[h] = str(val).strip() if val is not None else ""
                    if any(row_dict.values()):
                        rows.append(row_dict)
        elif ext == ".docx":
            import docx
            doc = docx.Document(io.BytesIO(raw_bytes))
            rows = []
            if doc.tables:
                table = doc.tables[0]
                if len(table.rows) >= self.config.header_row:
                    headers = [c.text.strip() for c in table.rows[self.config.header_row - 1].cells]
                    for r in table.rows[self.config.data_start_row - 1:]:
                        row_dict = {}
                        for i, h in enumerate(headers):
                            if i < len(r.cells) and h:
                                row_dict[h] = r.cells[i].text.strip()
                        if any(row_dict.values()):
                            rows.append(row_dict)
        else:
            raise ValueError(f"Unsupported structured template format: {ext}")

        return self.rows_to_ir(rows, title=Path(filename).stem)

    def parse_file(self, file_path: str, filename: str) -> ProcessIR:
        p = Path(file_path)
        if p.stat().st_size > MAX_DOC_FILE_SIZE:
            raise ValueError(f"File exceeds maximum allowed size of {MAX_DOC_FILE_SIZE // (1024 * 1024)}MB")

        ext = p.suffix.lower()
        if ext == ".csv":
            rows = self._read_csv(p)
        elif ext == ".xlsx":
            rows = self._read_xlsx(p)
        elif ext == ".docx":
            rows = self._read_docx(p)
        elif ext == ".json":
            rows = self._read_json(p)
        else:
            raise ValueError(f"Unsupported structured template format: {ext}")

        return self.rows_to_ir(rows, title=p.stem)

    def _read_csv(self, path: Path) -> List[Dict[str, str]]:
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(content))
        all_lines = [r for r in reader if any(cell.strip() for cell in r)]
        if not all_lines:
            return []
        headers = [h.strip() for h in all_lines[self.config.header_row - 1]]
        data_rows = all_lines[self.config.data_start_row - 1:]

        result: List[Dict[str, str]] = []
        for r in data_rows:
            row_dict = {}
            for i, h in enumerate(headers):
                if i < len(r):
                    row_dict[h] = r[i].strip()
            if row_dict:
                result.append(row_dict)
        return result

    def _read_xlsx(self, path: Path) -> List[Dict[str, str]]:
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required to parse .xlsx templates")

        # data_only=True prevents macro execution and reads evaluated formulas
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        sheet = wb[self.config.sheet_name] if self.config.sheet_name and self.config.sheet_name in wb.sheetnames else wb.active

        rows: List[List[Any]] = []
        for r in sheet.iter_rows(values_only=True):
            if r and any(cell is not None for cell in r):
                rows.append([str(c).strip() if c is not None else "" for c in r])

        if not rows:
            return []

        headers = [h for h in rows[self.config.header_row - 1]]
        data_rows = rows[self.config.data_start_row - 1:]

        result: List[Dict[str, str]] = []
        for r in data_rows:
            row_dict = {}
            for i, h in enumerate(headers):
                if i < len(r) and h:
                    row_dict[h] = r[i]
            if row_dict:
                result.append(row_dict)
        return result

    def _read_docx(self, path: Path) -> List[Dict[str, str]]:
        try:
            import docx
        except ImportError:
            raise ImportError("python-docx is required to parse .docx templates")

        doc = docx.Document(path)
        if not doc.tables:
            raise ValueError("No table found in docx template")

        table = doc.tables[0]
        rows: List[List[str]] = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                rows.append(cells)

        if not rows:
            return []

        headers = rows[self.config.header_row - 1]
        data_rows = rows[self.config.data_start_row - 1:]

        result: List[Dict[str, str]] = []
        for r in data_rows:
            row_dict = {}
            for i, h in enumerate(headers):
                if i < len(r) and h:
                    row_dict[h] = r[i]
            if row_dict:
                result.append(row_dict)
        return result

    def _read_json(self, path: Path) -> List[Dict[str, str]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [{str(k): str(v) for k, v in item.items()} for item in data if isinstance(item, dict)]
        elif isinstance(data, dict) and "steps" in data:
            return [{str(k): str(v) for k, v in item.items()} for item in data["steps"] if isinstance(item, dict)]
        return []

    def rows_to_ir(self, rows: List[Dict[str, str]], title: str = "Template Process") -> ProcessIR:
        """
        Maps normalized rows into ProcessIR according to column configuration.
        """
        if not rows:
            return ProcessIR(id="Process_1", name=title, description="Empty document template")

        # Map header names to IR fields. Exact alias matches win; otherwise a header that
        # contains an alias as a whole word (e.g. "Actor / Role", "Activity Name",
        # "Condition / Rule") is accepted so real-world spreadsheets map without editing.
        col_header_map: Dict[str, str] = {}  # ir_field -> matching header in row
        sample_row = rows[0]
        headers = list(sample_row.keys())

        def _norm(text: str) -> str:
            return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

        used_headers: set = set()
        for ir_field, col_def in self.config.columns.items():
            exact = None
            for alias in col_def.aliases:
                for h in headers:
                    if h not in used_headers and _norm(h) == _norm(alias):
                        exact = h
                        break
                if exact:
                    break
            if exact:
                col_header_map[ir_field] = exact
                used_headers.add(exact)
        for ir_field, col_def in self.config.columns.items():
            if ir_field in col_header_map:
                continue
            for alias in col_def.aliases:
                alias_n = _norm(alias)
                if len(alias_n) < 3:
                    continue
                for h in headers:
                    if h in used_headers:
                        continue
                    h_n = _norm(h)
                    if re.search(rf"(^| ){re.escape(alias_n)}( |$)", h_n):
                        col_header_map[ir_field] = h
                        used_headers.add(h)
                        break
                if ir_field in col_header_map:
                    break

        elements: List[FlowNode] = []
        flows: List[SequenceFlow] = []
        lanes_dict: Dict[str, str] = {}  # actor_name -> lane_id
        step_id_to_elem_id: Dict[str, str] = {}
        row_condition: Dict[str, str] = {}  # elem_id -> condition written on that row
        branch_gateways: List[FlowNode] = []  # gateways synthesised for multi-target rows

        # 1. Start Event
        start_event = FlowNode(
            id="Event_start",
            type="startEvent",
            name="Start",
            laneId="",
            confidence=1.0,
            sourceRefs=[SourceRef(sourceLocation="Template Ingestion", textSnippet="Process entry")]
        )
        elements.append(start_event)

        # 2. Build flow nodes
        for idx, row in enumerate(rows, start=1):
            def get_val(ir_f: str, def_val: str = "") -> str:
                h = col_header_map.get(ir_f)
                val = row.get(h, "") if h else ""
                return val.strip() if val else def_val

            raw_step_id = get_val("step_id", str(idx))
            activity_name = get_val("activity_name", f"Step {idx}")
            actor = get_val("role_actor", "General") or "General"
            raw_type = get_val("element_type", "task")
            is_decision = get_val("is_decision", "").lower() in ("true", "yes", "1", "y")
            system_val = get_val("system", "")
            doc_val = get_val("documentation", "")

            # Determine BPMN type
            elem_type = "task"
            if is_decision:
                elem_type = "exclusiveGateway"
            elif raw_type in self.config.columns.get("element_type", ColumnMapping()).mapping or {}:
                elem_type = self.config.columns["element_type"].mapping.get(raw_type, "task")
            elif raw_type in ("userTask", "serviceTask", "manualTask", "exclusiveGateway"):
                elem_type = raw_type

            # Create or get lane
            if actor not in lanes_dict:
                lanes_dict[actor] = f"Lane_{len(lanes_dict) + 1}"
            lane_id = lanes_dict[actor]

            elem_id = f"Activity_{idx}" if elem_type != "exclusiveGateway" else f"Gateway_{idx}"
            step_id_to_elem_id[raw_step_id] = elem_id
            step_id_to_elem_id[str(idx)] = elem_id
            row_condition[elem_id] = get_val("condition", "")

            desc = doc_val
            if system_val:
                desc = f"System: {system_val}. {desc}".strip()

            elements.append(
                FlowNode(
                    id=elem_id,
                    type=elem_type,
                    name=activity_name,
                    laneId=lane_id,
                    documentation=desc,
                    confidence=1.0,
                    sourceRefs=[
                        SourceRef(
                            sourceLocation=f"Row {idx}",
                            textSnippet=f"{raw_step_id}: {activity_name} ({actor})"
                        )
                    ]
                )
            )

        # 3. End Event
        end_event = FlowNode(
            id="Event_end",
            type="endEvent",
            name="End",
            laneId=list(lanes_dict.values())[-1] if lanes_dict else "",
            confidence=1.0,
            sourceRefs=[]
        )
        elements.append(end_event)

        # Set Start Event lane
        start_event.laneId = list(lanes_dict.values())[0] if lanes_dict else ""

        # 4. Synthesize Sequence Flows
        first_step_id = elements[1].id if len(elements) > 2 else "Event_end"
        flows.append(
            SequenceFlow(
                id=f"Flow_Start_{first_step_id}",
                sourceId="Event_start",
                targetId=first_step_id
            )
        )

        for idx, row in enumerate(rows, start=1):
            def get_val(ir_f: str, def_val: str = "") -> str:
                h = col_header_map.get(ir_f)
                val = row.get(h, "") if h else ""
                return val.strip() if val else def_val

            curr_elem_id = elements[idx].id  # elements[0] is startEvent
            next_steps_raw = get_val("next_steps", "")
            condition_val = get_val("condition", "")

            if next_steps_raw:
                # Accept "A, B", "A; B", "A / B" and "A | B" as multiple targets.
                targets = [t.strip() for t in re.split(r"[,;/|]", next_steps_raw) if t.strip()]
                resolved: List[str] = []
                for t in targets:
                    target_elem_id = step_id_to_elem_id.get(t)
                    if not target_elem_id and t.lower() in ("end", "finish", "done"):
                        target_elem_id = "Event_end"
                    if target_elem_id:
                        resolved.append(target_elem_id)

                source_elem = elements[idx]
                if len(resolved) > 1 and source_elem.type != "exclusiveGateway":
                    # A task with several successors is a decision: insert a gateway after it
                    # and label each branch with the condition written on the target row.
                    gw_id = f"Gateway_{curr_elem_id}"
                    branch_gateways.append(
                        FlowNode(
                            id=gw_id,
                            type="exclusiveGateway",
                            name=f"{source_elem.name}?",
                            laneId=source_elem.laneId,
                            confidence=1.0,
                            sourceRefs=list(source_elem.sourceRefs),
                        )
                    )
                    flows.append(SequenceFlow(id=f"Flow_{curr_elem_id}_{gw_id}", sourceId=curr_elem_id, targetId=gw_id))
                    for target_elem_id in resolved:
                        label = row_condition.get(target_elem_id, "") or condition_val
                        flows.append(
                            SequenceFlow(
                                id=f"Flow_{gw_id}_{target_elem_id}",
                                sourceId=gw_id,
                                targetId=target_elem_id,
                                name=label,
                                condition=label,
                            )
                        )
                else:
                    for target_elem_id in resolved:
                        label = condition_val
                        if source_elem.type == "exclusiveGateway" and not label:
                            label = row_condition.get(target_elem_id, "")
                        flows.append(
                            SequenceFlow(
                                id=f"Flow_{curr_elem_id}_{target_elem_id}",
                                sourceId=curr_elem_id,
                                targetId=target_elem_id,
                                name=label if source_elem.type == "exclusiveGateway" else "",
                                condition=label,
                            )
                        )
            elif idx < len(rows):
                # Sequential default connection
                next_elem_id = elements[idx + 1].id
                flows.append(
                    SequenceFlow(
                        id=f"Flow_{curr_elem_id}_{next_elem_id}",
                        sourceId=curr_elem_id,
                        targetId=next_elem_id,
                        condition=condition_val
                    )
                )
            else:
                # Last step connects to endEvent
                flows.append(
                    SequenceFlow(
                        id=f"Flow_{curr_elem_id}_Event_end",
                        sourceId=curr_elem_id,
                        targetId="Event_end"
                    )
                )

        # 5. Build Pools & Lanes
        lanes = [Lane(id=lid, name=actor) for actor, lid in lanes_dict.items()]
        pools = [
            Pool(
                id="Participant_1",
                name=title,
                lanes=lanes
            )
        ]

        elements.extend(branch_gateways)

        return ProcessIR(
            id="Process_1",
            name=title,
            description=f"Direct deterministic parse from structured template ({self.config.template_name})",
            pools=pools,
            elements=elements,
            flows=flows
        )
