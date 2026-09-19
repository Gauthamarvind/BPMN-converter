"""
Template Local Storage Manager.
Handles saving, listing, reading, and deleting templates under data/templates/<template_id>/.
Ships one built-in reference template (Celonis); users upload their own for other tools.
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
from backend.identity import safe_identifier, slugify, LOCAL_USER

_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "templates"


# Built-in reference template (scope v2: Celonis is the only bundled vendor template)
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

    Every public method that takes a ``template_id`` validates it with
    ``safe_identifier`` and checks the resolved path stays inside ``root_dir`` — a
    template id is a directory name, so ``..`` must never reach the filesystem.

    Multi-user scoping: built-in templates (``is_builtin``) are visible to everyone and
    cannot be deleted. Uploaded templates carry ``owner_id`` and are only listed, used,
    and deleted by their owner (``LOCAL_USER`` sees everything, which keeps the
    single-user setup unchanged). "Default" is stored per user under ``_prefs/``.
    """

    PREFS_DIR = "_prefs"

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = Path(root_dir or _DEFAULT_STORAGE_DIR).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        (self.root_dir / self.PREFS_DIR).mkdir(parents=True, exist_ok=True)
        self._ensure_defaults()

    # ------------------------------------------------------------------ helpers
    def _folder(self, template_id: str) -> Path:
        tid = safe_identifier(template_id, "template id")
        folder = (self.root_dir / tid).resolve()
        if folder.parent != self.root_dir:
            raise ValueError(f"Invalid template id '{template_id}'.")
        return folder

    @staticmethod
    def _can_see(meta: TemplateMetadata, user_id: Optional[str]) -> bool:
        if user_id in (None, LOCAL_USER):
            return True
        return meta.is_builtin or not meta.owner_id or meta.owner_id == user_id

    @staticmethod
    def _can_modify(meta: TemplateMetadata, user_id: Optional[str]) -> bool:
        if meta.is_builtin:
            return user_id in (None, LOCAL_USER)
        if user_id in (None, LOCAL_USER):
            return True
        return meta.owner_id == user_id

    def _prefs_file(self, user_id: str) -> Path:
        return self.root_dir / self.PREFS_DIR / f"{slugify(user_id, 'user', 80)}.json"

    def _read_prefs(self, user_id: str) -> Dict[str, Any]:
        f = self._prefs_file(user_id)
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _write_prefs(self, user_id: str, prefs: Dict[str, Any]) -> None:
        self._prefs_file(user_id).write_text(json.dumps(prefs, indent=2), encoding="utf-8")

    def _read_meta(self, folder: Path) -> Optional[TemplateMetadata]:
        meta_file = folder / "metadata.json"
        if not meta_file.exists():
            return None
        try:
            return TemplateMetadata(**json.loads(meta_file.read_text(encoding="utf-8")))
        except Exception:
            return None

    # Built-in templates that shipped before scope v2 and are no longer supported.
    RETIRED_BUILTINS = ("default_camunda", "default_signavio", "default_aris")

    def _prune_retired_builtins(self):
        """Removes built-in vendor templates dropped in scope v2 from existing installs."""
        for tid in self.RETIRED_BUILTINS:
            folder = self.root_dir / tid
            if not folder.exists():
                continue
            meta = self._read_meta(folder)
            if meta is None or meta.is_builtin:
                shutil.rmtree(folder, ignore_errors=True)

    def _ensure_defaults(self):
        """Initializes built-in templates if not already present."""
        self._prune_retired_builtins()
        defaults = [
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
                    is_default=(tid == "default_celonis"),
                    is_builtin=True,
                )
            else:
                # Older installs have no is_builtin flag; stamp it so they cannot be deleted.
                meta = self._read_meta(folder)
                if meta and not meta.is_builtin:
                    meta.is_builtin = True
                    (folder / "metadata.json").write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ queries
    def list_templates(self, user_id: Optional[str] = None) -> List[TemplateMetadata]:
        results: List[TemplateMetadata] = []
        if not self.root_dir.exists():
            return results
        prefs = self._read_prefs(user_id) if user_id else {}
        user_default = prefs.get("default_template_id")

        for sub in sorted(self.root_dir.iterdir()):
            if not sub.is_dir() or sub.name.startswith("_"):
                continue
            meta = self._read_meta(sub)
            if not meta or not self._can_see(meta, user_id):
                continue
            if user_default:
                meta.is_default = (meta.id == user_default)
            results.append(meta)
        return results

    def get_template(self, template_id: str, user_id: Optional[str] = None) -> Optional[Tuple[TemplateMetadata, str, TemplateSpec]]:
        try:
            folder = self._folder(template_id)
        except ValueError:
            return None
        if not folder.exists():
            return None

        meta = self._read_meta(folder)
        if not meta or not self._can_see(meta, user_id):
            return None

        template_file = folder / Path(meta.filename).name
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

    # ------------------------------------------------------------------ writes
    def save_template(
        self,
        xml_content: str,
        filename: str = "template.bpmn",
        name: Optional[str] = None,
        description: str = "",
        owner_id: str = "",
    ) -> Tuple[TemplateMetadata, TemplateDetectionReport]:
        """
        Registers an uploaded reference BPMN file under a generated, path-safe id
        (``tpl_<slug>_<timestamp>``). Called by ``POST /api/templates``.
        """
        stem = Path(filename or "template.bpmn").stem
        display_name = (name or "").strip() or stem.replace("_", " ").strip() or "Reference Template"
        template_id = f"tpl_{slugify(display_name)}_{int(time.time() * 1000) % 100000000}"
        safe_filename = f"{slugify(stem, 'template')}.bpmn"
        return self.save_bpmn_template(
            template_id=template_id,
            name=display_name,
            xml_content=xml_content,
            filename=safe_filename,
            is_default=False,
            description=description,
            owner_id=owner_id,
        )

    def save_bpmn_template(
        self,
        template_id: str,
        name: str,
        xml_content: str,
        filename: str = "template.bpmn",
        is_default: bool = False,
        description: str = "",
        owner_id: str = "",
        is_builtin: bool = False,
    ) -> Tuple[TemplateMetadata, TemplateDetectionReport]:
        folder = self._folder(template_id)
        filename = Path(filename).name or "template.bpmn"

        # Parse (and reject unsafe XML) before touching the disk
        parser = BpmnTemplateParser(template_id, name, xml_content)
        spec, report = parser.parse()

        folder.mkdir(parents=True, exist_ok=True)

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
            skeleton_count=len(spec.skeleton_nodes),
            owner_id=owner_id or "",
            is_builtin=is_builtin,
        )

        meta_file = folder / "metadata.json"
        meta_file.write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")

        return meta, report

    def delete_template(self, template_id: str, user_id: Optional[str] = None) -> bool:
        """Returns True when deleted. Raises PermissionError for built-ins / other users' templates."""
        folder = self._folder(template_id)
        if not folder.exists():
            return False
        meta = self._read_meta(folder)
        if meta and not self._can_modify(meta, user_id):
            raise PermissionError("You cannot delete this template.")
        shutil.rmtree(folder, ignore_errors=True)
        return True

    def set_default(self, template_id: str, user_id: Optional[str] = None) -> bool:
        """
        Marks a template as the caller's default. For the single-user setup the flag is
        written to the metadata files (as before); for identified users it is stored in
        their own preferences so one person's choice never changes another's.
        """
        folder = self._folder(template_id)
        meta = self._read_meta(folder) if folder.exists() else None
        if not meta or not self._can_see(meta, user_id):
            return False

        if user_id in (None, LOCAL_USER):
            for sub in self.root_dir.iterdir():
                if sub.is_dir() and not sub.name.startswith("_"):
                    m = self._read_meta(sub)
                    if m:
                        m.is_default = (m.id == template_id)
                        (sub / "metadata.json").write_text(json.dumps(m.model_dump(), indent=2), encoding="utf-8")
            return True

        prefs = self._read_prefs(user_id)
        prefs["default_template_id"] = template_id
        self._write_prefs(user_id, prefs)
        return True
