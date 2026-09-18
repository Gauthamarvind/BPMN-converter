"""
Template Mode Package for Process2BPMN.
Supports BPMN reference templates and structured document templates (.xlsx, .docx, .csv, .json).
"""

import sys
from backend.templates.models import (
    TemplateSpec,
    TemplateMetadata,
    TemplateDetectionReport,
    TemplateBindings,
    LaneMappingResult,
    DocumentTemplateConfig,
    LaneMetric,
    PoolMetric,
    SkeletonNode
)
from backend.templates.bpmn_parser import BpmnTemplateParser
from backend.templates.bpmn_renderer import BpmnTemplateRenderer
from backend.templates.doc_parser import DocTemplateParser, load_template_config
from backend.templates.mapper import LaneMapper
from backend.templates.storage import TemplateStorage
from backend.templates.blank_generator import generate_blank_xlsx, generate_blank_docx

# Support both import paths: backend.templates and app.templates
sys.modules["app.templates"] = sys.modules[__name__]

__all__ = [
    "TemplateSpec",
    "TemplateMetadata",
    "TemplateDetectionReport",
    "TemplateBindings",
    "LaneMappingResult",
    "DocumentTemplateConfig",
    "LaneMetric",
    "PoolMetric",
    "SkeletonNode",
    "BpmnTemplateParser",
    "BpmnTemplateRenderer",
    "DocTemplateParser",
    "load_template_config",
    "LaneMapper",
    "TemplateStorage",
    "generate_blank_xlsx",
    "generate_blank_docx"
]
