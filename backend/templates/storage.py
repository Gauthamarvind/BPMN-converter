"""
Template Local Storage Manager.
Handles saving, listing, reading, and deleting templates under data/templates/<template_id>/.
Includes default reference templates for Camunda, Signavio, ARIS, and Celonis.
"""

from __future__ import annotations
import json
import os
import shutil
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from backend.templates.models import (
    TemplateMetadata,
    TemplateSpec,
    TemplateDetectionReport
)
from backend.templates.bpmn_parser import BpmnTemplateParser
from backend.templates.profile_derivator import derive_profile_from_template

_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "templates"


# Pre-packaged BPMN templates for the 4 target tools
CAMUNDA_SAMPLE_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
                  id="Definitions_Camunda_Template"
                  targetNamespace="http://bpmn.io/schema/bpmn"
                  exporter="Camunda Modeler"
                  exporterVersion="5.20.0">
  <bpmn:collaboration id="Collaboration_Camunda_Template">
    <bpmn:participant id="Participant_Camunda" name="Camunda Standard Enterprise Process" processRef="Process_Camunda_Template"/>
  </bpmn:collaboration>
  <bpmn:process id="Process_Camunda_Template" isExecutable="true">
    <bpmn:laneSet id="LaneSet_Camunda">
      <bpmn:lane id="Lane_Initiator" name="Initiator">
        <bpmn:flowNodeRef>Event_Start_Fixed</bpmn:flowNodeRef>
      </bpmn:lane>
      <bpmn:lane id="Lane_Approver" name="Approver"/>
      <bpmn:lane id="Lane_System" name="Automated Service"/>
    </bpmn:laneSet>
    <bpmn:startEvent id="Event_Start_Fixed" name="Case Opened">
      <bpmn:outgoing>Flow_Start_Init</bpmn:outgoing>
    </bpmn:startEvent>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_Camunda">
    <bpmndi:BPMNPlane id="BPMNPlane_Camunda" bpmnElement="Collaboration_Camunda_Template">
      <bpmndi:BPMNShape id="Shape_Participant_Camunda" bpmnElement="Participant_Camunda" isHorizontal="true">
        <dc:Bounds x="120" y="80" width="1300" height="540"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Initiator" bpmnElement="Lane_Initiator" isHorizontal="true">
        <dc:Bounds x="150" y="80" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Approver" bpmnElement="Lane_Approver" isHorizontal="true">
        <dc:Bounds x="150" y="260" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_System" bpmnElement="Lane_System" isHorizontal="true">
        <dc:Bounds x="150" y="440" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Event_Start_Fixed" bpmnElement="Event_Start_Fixed">
        <dc:Bounds x="210" y="152" width="36" height="36"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""

SIGNAVIO_SAMPLE_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:signavio="http://www.signavio.com"
                  id="Definitions_Signavio_Template"
                  targetNamespace="http://www.signavio.com/bpmn20"
                  exporter="Signavio Process Editor"
                  exporterVersion="14.3.0">
  <bpmn:collaboration id="Collaboration_Signavio_Template">
    <bpmn:participant id="Participant_Signavio" name="Signavio Corporate Process" processRef="Process_Signavio_Template"/>
  </bpmn:collaboration>
  <bpmn:process id="Process_Signavio_Template" isExecutable="false">
    <bpmn:laneSet id="LaneSet_Signavio">
      <bpmn:lane id="Lane_Customer_Service" name="Customer Service">
        <bpmn:flowNodeRef>Event_Customer_Call</bpmn:flowNodeRef>
      </bpmn:lane>
      <bpmn:lane id="Lane_Operations" name="Operations"/>
      <bpmn:lane id="Lane_Finance" name="Finance"/>
    </bpmn:laneSet>
    <bpmn:startEvent id="Event_Customer_Call" name="Customer Inquiry Received"/>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_Signavio">
    <bpmndi:BPMNPlane id="BPMNPlane_Signavio" bpmnElement="Collaboration_Signavio_Template">
      <bpmndi:BPMNShape id="Shape_Participant_Signavio" bpmnElement="Participant_Signavio" isHorizontal="true">
        <dc:Bounds x="120" y="80" width="1350" height="540"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_CS" bpmnElement="Lane_Customer_Service" isHorizontal="true">
        <dc:Bounds x="150" y="80" width="1320" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Ops" bpmnElement="Lane_Operations" isHorizontal="true">
        <dc:Bounds x="150" y="260" width="1320" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Fin" bpmnElement="Lane_Finance" isHorizontal="true">
        <dc:Bounds x="150" y="440" width="1320" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Event_Call" bpmnElement="Event_Customer_Call">
        <dc:Bounds x="210" y="152" width="30" height="30"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""

ARIS_SAMPLE_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:aris="http://www.ids-scheer.com/aris"
                  id="Definitions_ARIS_Template"
                  targetNamespace="http://www.ids-scheer.com/aris"
                  exporter="ARIS Architect"
                  exporterVersion="10.0">
  <bpmn:collaboration id="Collaboration_ARIS">
    <bpmn:participant id="Participant_ARIS" name="ARIS Enterprise Framework" processRef="Process_ARIS"/>
  </bpmn:collaboration>
  <bpmn:process id="Process_ARIS" isExecutable="false">
    <bpmn:laneSet id="LaneSet_ARIS">
      <bpmn:lane id="Lane_Requestor" name="Requester"/>
      <bpmn:lane id="Lane_Fulfillment" name="Fulfillment Team"/>
      <bpmn:lane id="Lane_Auditing" name="Compliance and Audit"/>
    </bpmn:laneSet>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_ARIS">
    <bpmndi:BPMNPlane id="BPMNPlane_ARIS" bpmnElement="Collaboration_ARIS">
      <bpmndi:BPMNShape id="Shape_Participant_ARIS" bpmnElement="Participant_ARIS" isHorizontal="true">
        <dc:Bounds x="100" y="80" width="1300" height="540"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_ARIS_1" bpmnElement="Lane_Requestor" isHorizontal="true">
        <dc:Bounds x="130" y="80" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_ARIS_2" bpmnElement="Lane_Fulfillment" isHorizontal="true">
        <dc:Bounds x="130" y="260" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_ARIS_3" bpmnElement="Lane_Auditing" isHorizontal="true">
        <dc:Bounds x="130" y="440" width="1270" height="180"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""

CELONIS_SAMPLE_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_Celonis_Template"
                  targetNamespace="http://celonis.com/schema/bpmn"
                  exporter="Celonis Process Mining"
                  exporterVersion="4.8">
  <bpmn:collaboration id="Collaboration_Celonis">
    <bpmn:participant id="Participant_Celonis" name="Order to Cash Template" processRef="Process_Celonis"/>
  </bpmn:collaboration>
  <bpmn:process id="Process_Celonis" isExecutable="false">
    <bpmn:laneSet id="LaneSet_Celonis">
      <bpmn:lane id="Lane_Sales_Order" name="Sales Order Processing"/>
      <bpmn:lane id="Lane_Logistics" name="Logistics and Warehousing"/>
      <bpmn:lane id="Lane_Invoicing" name="Accounts Receivable"/>
    </bpmn:laneSet>
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_Celonis">
    <bpmndi:BPMNPlane id="BPMNPlane_Celonis" bpmnElement="Collaboration_Celonis">
      <bpmndi:BPMNShape id="Shape_Participant_Celonis" bpmnElement="Participant_Celonis" isHorizontal="true">
        <dc:Bounds x="100" y="80" width="1300" height="540"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Celonis_1" bpmnElement="Lane_Sales_Order" isHorizontal="true">
        <dc:Bounds x="130" y="80" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Celonis_2" bpmnElement="Lane_Logistics" isHorizontal="true">
        <dc:Bounds x="130" y="260" width="1270" height="180"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Shape_Lane_Celonis_3" bpmnElement="Lane_Invoicing" isHorizontal="true">
        <dc:Bounds x="130" y="440" width="1270" height="180"/>
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""


class TemplateStorage:
    """
    Manages filesystem storage for templates in /data/templates/<id>/
    """

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = Path(root_dir or _DEFAULT_STORAGE_DIR)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Initializes built-in templates if not already present."""
        defaults = [
            ("default_camunda", "Camunda 8 Reference Template", "camunda", CAMUNDA_SAMPLE_BPMN),
            ("default_signavio", "SAP Signavio Standard Template", "signavio", SIGNAVIO_SAMPLE_BPMN),
            ("default_aris", "ARIS Process Governance Template", "aris", ARIS_SAMPLE_BPMN),
            ("default_celonis", "Celonis EMS Execution Template", "celonis", CELONIS_SAMPLE_BPMN),
        ]
        for tid, name, vendor, xml_content in defaults:
            folder = self.root_dir / tid
            if not folder.exists():
                self.save_bpmn_template(
                    template_id=tid,
                    name=name,
                    xml_content=xml_content,
                    filename=f"{tid}.bpmn",
                    is_default=(tid == "default_camunda")
                )

    def list_templates(self) -> List[TemplateMetadata]:
        results: List[TemplateMetadata] = []
        if not self.root_dir.exists():
            return results

        for sub in sorted(self.root_dir.iterdir()):
            if sub.is_dir():
                meta_file = sub / "metadata.json"
                if meta_file.exists():
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        results.append(TemplateMetadata(**data))
                    except Exception:
                        pass
        return results

    def get_template(self, template_id: str) -> Optional[Tuple[TemplateMetadata, str, TemplateSpec]]:
        folder = self.root_dir / template_id
        if not folder.exists():
            return None

        meta_file = folder / "metadata.json"
        if not meta_file.exists():
            return None

        meta = TemplateMetadata(**json.loads(meta_file.read_text(encoding="utf-8")))

        template_file = folder / meta.filename
        if not template_file.exists():
            return None

        content = template_file.read_text(encoding="utf-8")
        spec_file = folder / "spec.json"
        if spec_file.exists():
            spec = TemplateSpec(**json.loads(spec_file.read_text(encoding="utf-8")))
        else:
            parser = BpmnTemplateParser(meta.id, meta.name, content)
            spec, _ = parser.parse()

        return meta, content, spec

    def save_bpmn_template(
        self,
        template_id: str,
        name: str,
        xml_content: str,
        filename: str = "template.bpmn",
        is_default: bool = False,
        description: str = ""
    ) -> Tuple[TemplateMetadata, TemplateDetectionReport]:
        folder = self.root_dir / template_id
        folder.mkdir(parents=True, exist_ok=True)

        parser = BpmnTemplateParser(template_id, name, xml_content)
        spec, report = parser.parse()

        # Save template file
        dest_file = folder / filename
        dest_file.write_text(xml_content, encoding="utf-8")

        # Save spec
        spec_file = folder / "spec.json"
        spec_file.write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")

        # Save derived profile
        derived_profile = derive_profile_from_template(spec)
        profile_file = folder / "profile.json"
        profile_file.write_text(json.dumps(derived_profile, indent=2), encoding="utf-8")

        # Save metadata
        meta = TemplateMetadata(
            id=template_id,
            name=name,
            type="bpmn",
            source_vendor=spec.source_vendor,
            upload_date=time.strftime("%Y-%m-%d %H:%M:%S"),
            filename=filename,
            is_default=is_default,
            derived_profile=derived_profile.get("profile_id"),
            description=description or f"Reference BPMN template conforming to {spec.source_vendor.title()}",
            pools_count=len(spec.pools),
            lanes_count=len(spec.get_all_lanes()),
            skeleton_count=len(spec.skeleton_nodes)
        )

        meta_file = folder / "metadata.json"
        meta_file.write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")

        return meta, report

    def delete_template(self, template_id: str) -> bool:
        folder = self.root_dir / template_id
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            return True
        return False

    def set_default(self, template_id: str) -> bool:
        found = False
        for sub in self.root_dir.iterdir():
            if sub.is_dir():
                meta_file = sub / "metadata.json"
                if meta_file.exists():
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        data["is_default"] = (data.get("id") == template_id)
                        meta_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        if data["is_default"]:
                            found = True
                    except Exception:
                        pass
        return found
