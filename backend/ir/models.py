"""
Process Intermediate Representation (Process IR) Models.
Strictly defines schema, constraints, NCName ID rules, and BPMN element types.
"""

from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
import re
import json

from pydantic import BaseModel, Field, field_validator


NCNAME_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.-]*$")

ALLOWED_ELEMENT_TYPES = (
    "startEvent",
    "endEvent",
    "intermediateTimerEvent",
    "intermediateMessageEvent",
    "task",
    "userTask",
    "serviceTask",
    "manualTask",
    "sendTask",
    "receiveTask",
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "subProcess",
    "callActivity"
)

ElementType = Literal[
    "startEvent",
    "endEvent",
    "intermediateTimerEvent",
    "intermediateMessageEvent",
    "task",
    "userTask",
    "serviceTask",
    "manualTask",
    "sendTask",
    "receiveTask",
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "subProcess",
    "callActivity"
]


class SourceRef(BaseModel):
    sourceLocation: str = ""
    textSnippet: str = ""


class FlowNode(BaseModel):
    id: str
    type: ElementType
    name: str
    laneId: str = ""
    documentation: str = ""
    confidence: float = 1.0
    sourceRefs: List[SourceRef] = Field(default_factory=list)


class SequenceFlow(BaseModel):
    id: str
    type: Literal["sequence", "message"] = "sequence"
    sourceId: str
    targetId: str
    name: str = ""
    condition: str = ""
    isDefault: bool = False


class Lane(BaseModel):
    id: str
    name: str


class Pool(BaseModel):
    id: str
    name: str
    lanes: List[Lane] = Field(default_factory=list)


class DataObject(BaseModel):
    id: str
    name: str
    itemSubjectRef: str = ""


class OpenQuestion(BaseModel):
    topic: str
    question: str
    suggestedAssumption: str = ""


class TemplateBindings(BaseModel):
    templateId: str
    laneMap: Dict[str, str] = Field(default_factory=dict)
    reuseSkeletonNodes: bool = True


class ProcessIR(BaseModel):
    id: str = "Process_1"
    name: str = "Extracted Business Process"
    description: str = ""
    pools: List[Pool] = Field(default_factory=list)
    elements: List[FlowNode] = Field(default_factory=list)
    flows: List[SequenceFlow] = Field(default_factory=list)
    dataObjects: List[DataObject] = Field(default_factory=list)
    openQuestions: List[OpenQuestion] = Field(default_factory=list)
    templateBindings: Optional[TemplateBindings] = None

    def to_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return json.loads(json.dumps(self, default=lambda o: getattr(o, "__dict__", str(o))))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessIR":
        pools = []
        for p in data.get("pools", []):
            lanes = [Lane(id=l.get("id", ""), name=l.get("name", "")) for l in p.get("lanes", [])]
            pools.append(Pool(id=p.get("id", ""), name=p.get("name", ""), lanes=lanes))
        
        elements = []
        for e in data.get("elements", []):
            sources = [
                SourceRef(
                    sourceLocation=s.get("sourceLocation", ""),
                    textSnippet=s.get("textSnippet", "")
                )
                for s in e.get("sourceRefs", [])
            ]
            elements.append(
                FlowNode(
                    id=e.get("id", ""),
                    type=e.get("type", "task"),
                    name=e.get("name", ""),
                    laneId=e.get("laneId", ""),
                    documentation=e.get("documentation", ""),
                    confidence=float(e.get("confidence", 1.0)),
                    sourceRefs=sources
                )
            )

        flows = []
        for f in data.get("flows", []):
            flows.append(
                SequenceFlow(
                    id=f.get("id", ""),
                    type=f.get("type", "sequence"),
                    sourceId=f.get("sourceId", ""),
                    targetId=f.get("targetId", ""),
                    name=f.get("name", ""),
                    condition=f.get("condition", ""),
                    isDefault=bool(f.get("isDefault", False))
                )
            )

        data_objects = [
            DataObject(id=d.get("id", ""), name=d.get("name", ""), itemSubjectRef=d.get("itemSubjectRef", ""))
            for d in data.get("dataObjects", [])
        ]

        open_questions = [
            OpenQuestion(
                topic=q.get("topic", ""),
                question=q.get("question", ""),
                suggestedAssumption=q.get("suggestedAssumption", "")
            )
            for q in data.get("openQuestions", [])
        ]

        template_bindings = None
        tb_data = data.get("templateBindings")
        if tb_data and isinstance(tb_data, dict):
            template_bindings = TemplateBindings(
                templateId=tb_data.get("templateId", ""),
                laneMap=tb_data.get("laneMap", {}),
                reuseSkeletonNodes=bool(tb_data.get("reuseSkeletonNodes", True))
            )

        return cls(
            id=data.get("id", "Process_1"),
            name=data.get("name", "Extracted Business Process"),
            description=data.get("description", ""),
            pools=pools,
            elements=elements,
            flows=flows,
            dataObjects=data_objects,
            openQuestions=open_questions,
            templateBindings=template_bindings
        )
