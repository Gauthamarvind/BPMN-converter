"""
Profile Derivator: Auto-derives an export profile from a BPMN TemplateSpec.
Detects vendor extensions, namespaces, and exporter metadata.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
from backend.templates.models import TemplateSpec


def derive_profile_from_template(spec: TemplateSpec) -> Dict[str, Any]:
    """
    Analyzes namespaces and exporter in a TemplateSpec to generate or link a target profile.
    """
    ns_str = " ".join(spec.namespaces.values()).lower()
    exporter_str = (spec.exporter or "").lower()
    vendor_lower = spec.source_vendor.lower()

    if "camunda" in ns_str or "camunda" in exporter_str or vendor_lower == "camunda":
        target = "camunda"
        display = f"Camunda Conformance ({spec.name})"
    elif "signavio" in ns_str or "signavio" in exporter_str or vendor_lower == "signavio":
        target = "signavio"
        display = f"Signavio Conformance ({spec.name})"
    elif "aris" in ns_str or "aris" in exporter_str or "ids-scheer" in ns_str or vendor_lower == "aris":
        target = "aris"
        display = f"ARIS Conformance ({spec.name})"
    elif "celonis" in ns_str or "celonis" in exporter_str or vendor_lower == "celonis":
        target = "celonis"
        display = f"Celonis Conformance ({spec.name})"
    else:
        target = "generic"
        display = f"Standard BPMN 2.0 Conformance ({spec.name})"

    return {
        "profile_id": f"profile_{spec.template_id}",
        "base_profile": target,
        "displayName": display,
        "source_vendor": target,
        "targetVendor": spec.source_vendor,
        "custom_namespaces": spec.namespaces,
        "exporter": spec.exporter or "Process2BPMN Template Engine",
        "exporterVersion": spec.exporter_version or "1.0",
        "description": f"Auto-derived export profile from reference template '{spec.name}'."
    }
