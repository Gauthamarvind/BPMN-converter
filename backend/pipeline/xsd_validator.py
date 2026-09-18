"""
BPMN 2.0 XML Schema (XSD) Validator.
Validates generated or input BPMN 2.0 XML against the official OMG BPMN20.xsd schema.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import xmlschema


class BpmnSchemaConfigurationError(RuntimeError):
    """Raised when BPMN 2.0 XSD schema files are missing or cannot be loaded."""
    pass


class BpmnSchemaError(ValueError):
    """Raised when BPMN 2.0 XML fails XSD validation."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or []
        self.kind = "BpmnSchemaError"


_SCHEMA_CACHE: Optional[xmlschema.XMLSchema] = None


def get_bpmn_schema() -> xmlschema.XMLSchema:
    """Loads and caches the BPMN 2.0 XMLSchema instance from backend/schemas/BPMN20.xsd."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schemas_dir = Path(__file__).resolve().parent.parent / "schemas"
    main_schema_file = schemas_dir / "BPMN20.xsd"
    required_files = ["BPMN20.xsd", "Semantic.xsd", "BPMNDI.xsd", "DI.xsd", "DC.xsd"]

    missing = [f for f in required_files if not (schemas_dir / f).is_file()]
    if missing:
        raise BpmnSchemaConfigurationError(
            f"BPMN 2.0 schema files missing in {schemas_dir}: {', '.join(missing)}. "
            "Run 'python scripts/fetch_bpmn_schemas.py' or 'make schemas'."
        )

    try:
        _SCHEMA_CACHE = xmlschema.XMLSchema(str(main_schema_file))
        return _SCHEMA_CACHE
    except Exception as ex:
        raise BpmnSchemaConfigurationError(
            f"Failed to load BPMN 2.0 schema from {main_schema_file}: {ex}"
        ) from ex


def validate_bpmn(xml_str: str) -> List[str]:
    """
    Validates a BPMN 2.0 XML string against official OMG XSD schemas.
    Returns a list of error message strings (empty list if valid).
    Raises BpmnSchemaConfigurationError if schema files are missing.
    """
    schema = get_bpmn_schema()
    errors: List[str] = []
    for err in schema.iter_errors(xml_str):
        msg = str(err.message if hasattr(err, "message") else err)
        errors.append(msg)
    return errors
