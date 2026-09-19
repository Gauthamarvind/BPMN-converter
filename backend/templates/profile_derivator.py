"""
Profile Derivator: Auto-derives an export profile from a BPMN TemplateSpec.
Detects vendor extensions, namespaces, and exporter metadata.

Scope v2: the only export targets are Celonis and generic BPMN 2.0. A template that came
from another tool (Camunda, Signavio, ARIS, ...) is still recognised — the vendor is kept
for display and for the import path — but its export base profile is the generic one.
"""

from __future__ import annotations
from typing import Dict, Any
from backend.templates.models import TemplateSpec


def detect_source_vendor(spec: TemplateSpec) -> str:
    """Returns the tool the template was exported from, or 'generic'."""
    ns_str = " ".join(spec.namespaces.values()).lower()
    exporter_str = (spec.exporter or "").lower()
    vendor_lower = (spec.source_vendor or "").lower()

    if "camunda" in ns_str or "camunda" in exporter_str or vendor_lower == "camunda":
        return "camunda"
    if "signavio" in ns_str or "signavio" in exporter_str or vendor_lower == "signavio":
        return "signavio"
    if "aris" in ns_str or "aris" in exporter_str or "ids-scheer" in ns_str or vendor_lower == "aris":
        return "aris"
    if "celonis" in ns_str or "celonis" in exporter_str or vendor_lower == "celonis":
        return "celonis"
    return "generic"


_DISPLAY = {
    "camunda": "Camunda",
    "signavio": "Signavio",
    "aris": "ARIS",
    "celonis": "Celonis",
    "generic": "Standard BPMN 2.0",
}


def derive_profile_from_template(spec: TemplateSpec) -> Dict[str, Any]:
    """
    Analyzes namespaces and exporter in a TemplateSpec to generate or link a target profile.
    """
    vendor = detect_source_vendor(spec)
    base_profile = "celonis" if vendor == "celonis" else "generic"
    display = f"{_DISPLAY[vendor]} Conformance ({spec.name})"

    return {
        "profile_id": f"profile_{spec.template_id}",
        "base_profile": base_profile,
        "displayName": display,
        "source_vendor": vendor,
        "targetVendor": spec.source_vendor,
        "custom_namespaces": spec.namespaces,
        "exporter": spec.exporter or "Process2BPMN Template Engine",
        "exporterVersion": spec.exporter_version or "1.0",
        "description": f"Auto-derived export profile from reference template '{spec.name}'.",
    }
