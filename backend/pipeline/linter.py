"""
Target-Tool Profile Loader and Compliance Linter.
Loads profiles from /profiles/*.yaml and audits Process IR against target tool constraints.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from backend.ir.models import ProcessIR

try:
    import yaml
    PYYAML_AVAILABLE = True
except ImportError:
    PYYAML_AVAILABLE = False


@dataclass
class ProfileWarning:
    level: str  # "WARNING", "INFO"
    rule: str
    message: str
    element_id: str = ""

    @property
    def severity(self) -> str:
        return self.level

    @property
    def code(self) -> str:
        return self.rule


@dataclass
class LintResult:
    profile_name: str
    display_name: str
    is_valid: bool
    warnings: List[ProfileWarning]
    assumptions: List[str]


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Lightweight fallback YAML parser for profile config structures."""
    result: Dict[str, Any] = {
        "allowedElementTypes": [],
        "extensionNamespaces": {},
        "assumptions": []
    }
    current_list: Optional[str] = None
    
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue

        if trimmed.startswith("allowedElementTypes:"):
            current_list = "allowedElementTypes"
            continue
        elif trimmed.startswith("assumptions:"):
            current_list = "assumptions"
            continue
        elif ":" in trimmed and not trimmed.startswith("-"):
            current_list = None
            key, val = trimmed.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val in ("{}", ""):
                result[key] = {}
            elif val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
            elif val.isdigit():
                result[key] = int(val)
            elif val:
                result[key] = val
        elif trimmed.startswith("-") and current_list:
            item = trimmed[1:].strip().strip('"').strip("'")
            result[current_list].append(item)

    return result


class ProfileLinter:
    """
    Loads profiles from /profiles/*.yaml and lints Process IR models.
    """

    def __init__(self, profiles_dir: Optional[str] = None):
        if profiles_dir:
            self.profiles_dir = Path(profiles_dir)
        else:
            # Default to /profiles relative to root
            self.profiles_dir = Path(__file__).resolve().parent.parent.parent / "profiles"

    def list_available_profiles(self) -> List[str]:
        if not self.profiles_dir.exists():
            return ["generic"]
        return [f.stem for f in self.profiles_dir.glob("*.yaml")]

    def load_profile(self, profile_name: str = "generic") -> Dict[str, Any]:
        file_path = self.profiles_dir / f"{profile_name}.yaml"
        if not file_path.exists():
            file_path = self.profiles_dir / "generic.yaml"

        if not file_path.exists():
            return {
                "name": "generic",
                "displayName": "Generic BPMN 2.0",
                "forceCollaboration": True,
                "maxLabelLength": 128,
                "conditionLocation": "conditionExpression",
                "allowedElementTypes": [
                    "startEvent", "endEvent", "intermediateTimerEvent", "intermediateMessageEvent",
                    "task", "userTask", "serviceTask", "manualTask", "sendTask", "receiveTask",
                    "exclusiveGateway", "parallelGateway", "inclusiveGateway", "subProcess", "callActivity"
                ],
                "assumptions": ["Standard BPMN 2.0 Analytic Subclass."]
            }

        content = file_path.read_text(encoding="utf-8")
        if PYYAML_AVAILABLE:
            data = yaml.safe_load(content) or {}
        else:
            data = parse_simple_yaml(content)
            
        return data

    def lint(self, ir: ProcessIR, profile_name: str = "generic") -> LintResult:
        profile = self.load_profile(profile_name)
        warnings: List[ProfileWarning] = []

        allowed_types = set(profile.get("allowedElementTypes", []))
        max_label_len = profile.get("maxLabelLength", 128)
        id_pattern_str = profile.get("idFormatPattern")
        id_pattern = re.compile(id_pattern_str) if id_pattern_str else None

        # 1. Element Type Checks
        if allowed_types:
            for elem in ir.elements:
                if elem.type not in allowed_types:
                    warnings.append(ProfileWarning(
                        level="WARNING",
                        rule="allowedElementTypes",
                        message=f"Element '{elem.name}' type '{elem.type}' is discouraged or unsupported by {profile.get('displayName', profile_name)}. Will be exported as standard task.",
                        element_id=elem.id
                    ))

        # 2. Label Length Checks
        for elem in ir.elements:
            if len(elem.name) > max_label_len:
                warnings.append(ProfileWarning(
                    level="INFO",
                    rule="maxLabelLength",
                    message=f"Element label '{elem.name[:25]}...' exceeds recommended {max_label_len} characters ({len(elem.name)} chars). Label will be truncated for display in this tool.",
                    element_id=elem.id
                ))

        for flow in ir.flows:
            if flow.name and len(flow.name) > max_label_len:
                warnings.append(ProfileWarning(
                    level="INFO",
                    rule="maxLabelLength",
                    message=f"Flow label '{flow.name[:25]}...' exceeds recommended {max_label_len} characters.",
                    element_id=flow.id
                ))

        # 3. ID Pattern Checks
        if id_pattern:
            for elem in ir.elements:
                if not id_pattern.match(elem.id):
                    warnings.append(ProfileWarning(
                        level="INFO",
                        rule="idFormatPattern",
                        message=f"Element ID '{elem.id}' does not match tool-preferred naming pattern.",
                        element_id=elem.id
                    ))

        return LintResult(
            profile_name=profile.get("name", profile_name),
            display_name=profile.get("displayName", profile_name.capitalize()),
            is_valid=len([w for w in warnings if w.level == "ERROR"]) == 0,
            warnings=warnings,
            assumptions=profile.get("assumptions", [])
        )
