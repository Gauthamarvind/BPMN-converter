"""
Template Models and Schemas for Process2BPMN Template Mode.
Defines TemplateSpec, DocumentTemplateConfig, TemplateMetadata, and LaneMappingResult.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
import re
from pydantic import BaseModel, Field
from backend.ir.models import TemplateBindings


class LaneMetric(BaseModel):
    id: str
    name: str
    order: int = 0
    height: float = 180.0
    y_offset: float = 0.0


class PoolMetric(BaseModel):
    id: str
    name: str
    width: float = 1200.0
    height: float = 540.0
    x: float = 100.0
    y: float = 100.0
    lanes: List[LaneMetric] = Field(default_factory=list)


class SkeletonNode(BaseModel):
    id: str
    type: str  # "startEvent", "endEvent", "subProcess", etc.
    name: str = ""
    lane_id: Optional[str] = None
    bounds: Dict[str, float] = Field(default_factory=dict)  # x, y, width, height
    is_fixed: bool = True
    incoming_flows: List[str] = Field(default_factory=list)
    outgoing_flows: List[str] = Field(default_factory=list)


class LayoutMetrics(BaseModel):
    orientation: str = "horizontal"  # "horizontal" or "vertical"
    default_lane_height: float = 180.0
    default_task_width: float = 100.0
    default_task_height: float = 80.0
    horizontal_spacing: float = 80.0
    vertical_spacing: float = 50.0
    id_pattern: str = r"^[a-zA-Z0-9_.-]+$"


class TemplateSpec(BaseModel):
    template_id: str
    name: str
    source_vendor: str = "generic"  # "signavio" | "camunda" | "aris" | "celonis" | "generic"
    namespaces: Dict[str, str] = Field(default_factory=dict)
    exporter: Optional[str] = None
    exporter_version: Optional[str] = None
    target_namespace: Optional[str] = None
    vendor_definitions_attrs: Dict[str, str] = Field(default_factory=dict)
    vendor_extension_elements_raw: Optional[str] = None
    pools: List[PoolMetric] = Field(default_factory=list)
    skeleton_nodes: List[SkeletonNode] = Field(default_factory=list)
    layout_metrics: LayoutMetrics = Field(default_factory=LayoutMetrics)
    derived_profile_id: Optional[str] = None

    def get_all_lanes(self) -> List[LaneMetric]:
        all_lanes: List[LaneMetric] = []
        for pool in self.pools:
            all_lanes.extend(pool.lanes)
        return all_lanes


class ColumnMapping(BaseModel):
    aliases: List[str] = Field(default_factory=list)
    required: bool = False
    default: Optional[str] = None
    type: str = "string"
    mapping: Optional[Dict[str, str]] = None
    delimiter: Optional[str] = None


class GapFillingConfig(BaseModel):
    auto_connect_sequential: bool = True
    llm_fill_missing_decisions: bool = True
    flag_inferred_fields: bool = True


class DocumentTemplateConfig(BaseModel):
    version: str = "1.0"
    template_name: str = "Standard Process Inventory Form"
    template_type: str = "document"  # "xlsx" | "csv" | "docx" | "json"
    description: str = ""
    sheet_name: Optional[str] = None
    header_row: int = 1
    data_start_row: int = 2
    comment_prefix: str = "#"
    columns: Dict[str, ColumnMapping] = Field(default_factory=dict)
    gap_filling: GapFillingConfig = Field(default_factory=GapFillingConfig)


class LaneMappingResult(BaseModel):
    actor: str
    lane_id: Optional[str] = None
    lane_name: Optional[str] = None
    confidence: float = 1.0
    match_type: str = "exact"  # "exact", "fuzzy", "llm", "new_lane", "unmatched"
    rationale: str = ""


class TemplateDetectionReport(BaseModel):
    template_id: str
    name: str
    template_type: str  # "bpmn" | "document"
    vendor: str = "generic"
    detected_namespaces: List[str] = Field(default_factory=list)
    pools_count: int = 0
    lanes: List[Dict[str, Any]] = Field(default_factory=list)
    skeleton_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    detected_columns: List[str] = Field(default_factory=list)
    valid_syntax: bool = True
    issues: List[str] = Field(default_factory=list)


class TemplateMetadata(BaseModel):
    id: str
    name: str
    type: str  # "bpmn" | "document"
    source_vendor: str = "generic"  # "signavio" | "camunda" | "aris" | "celonis" | "custom"
    upload_date: str = ""
    filename: str = ""
    is_default: bool = False
    owner_id: str = ""        # "" = built-in / shared; otherwise the uploading user's identity
    is_builtin: bool = False  # shipped with the app; cannot be deleted by users
    derived_profile: Optional[str] = None
    description: str = ""
    pools_count: int = 0
    lanes_count: int = 0
    skeleton_count: int = 0
