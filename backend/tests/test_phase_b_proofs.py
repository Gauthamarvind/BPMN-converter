"""
Verification Suite for Items B1 - B5:
- B1: XSD validation with xmlschema and OMG BPMN 2.0 schemas.
- B2: Serializer strict element order, timer duration handling, and DataObjects.
- B3: Single-pool vs Multi-pool configuration and serialization.
- B4: Validator policy (auto-fix safe items, report non-fixable errors with export_blocked).
- B5: Exporter metadata (exporter="Process2BPMN", exporterVersion) and NCName ID validation.
"""

from __future__ import annotations
import unittest
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.version import VERSION
from backend.config import config
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane, DataObject
from backend.pipeline.validator import ProcessValidator, sanitize_ncname
from backend.pipeline.layout import SugiyamaLayoutEngine
from backend.pipeline.serializer import BpmnXmlSerializer, BPMN_NS, BPMNDI_NS
from backend.pipeline.xsd_validator import validate_bpmn, BpmnSchemaError
from backend.pipeline.process_pipeline import process_pipeline


class TestPhaseBProofs(unittest.TestCase):

    def setUp(self):
        self.ncname_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")

    def test_b1_xsd_validation_valid_and_invalid(self):
        """B1 Proof: XSD validator accurately verifies compliant BPMN 2.0 XML and catches invalid XML."""
        ir = ProcessIR(
            id="proc_b1",
            name="Sample Valid Process",
            pools=[Pool(id="pool_1", name="Main Pool", lanes=[Lane(id="lane_1", name="Lane 1")])],
            elements=[
                FlowNode(id="start_1", name="Start", type="startEvent", laneId="lane_1"),
                FlowNode(id="task_1", name="Execute Task", type="task", laneId="lane_1"),
                FlowNode(id="end_1", name="End", type="endEvent", laneId="lane_1"),
            ],
            flows=[
                SequenceFlow(id="flow_1", sourceId="start_1", targetId="task_1"),
                SequenceFlow(id="flow_2", sourceId="task_1", targetId="end_1"),
            ]
        )
        layout = SugiyamaLayoutEngine(ir).compute_layout()
        serializer = BpmnXmlSerializer(ir, layout)
        xml_str = serializer.serialize()

        # Validate valid XML
        errors = validate_bpmn(xml_str)
        self.assertEqual(errors, [], f"Valid BPMN XML failed XSD validation: {errors}")

        # Validate invalid XML (e.g. invalid tag name)
        invalid_xml = xml_str.replace("bpmn:task", "bpmn:nonExistentTaskElement")
        invalid_errors = validate_bpmn(invalid_xml)
        self.assertTrue(len(invalid_errors) > 0, "Invalid XML should have produced XSD errors.")

    def test_b2_element_order_and_timer_durations_and_data_objects(self):
        """B2 Proof: FlowNode child ordering, timerDuration handling, and DataObjects serialization."""
        ir = ProcessIR(
            id="proc_b2",
            name="Timer and Data Process",
            pools=[Pool(id="pool_1", name="Pool 1", lanes=[Lane(id="lane_1", name="Lane 1")])],
            elements=[
                FlowNode(
                    id="start_1",
                    name="Start",
                    type="startEvent",
                    laneId="lane_1",
                    documentation="Starting documentation"
                ),
                FlowNode(
                    id="timer_1",
                    name="Wait 2 Hours",
                    type="intermediateTimerEvent",
                    laneId="lane_1",
                    timerDuration="PT2H"
                ),
                FlowNode(
                    id="timer_empty",
                    name="Empty Timer",
                    type="intermediateTimerEvent",
                    laneId="lane_1"
                ),
                FlowNode(
                    id="end_1",
                    name="End",
                    type="endEvent",
                    laneId="lane_1"
                ),
            ],
            flows=[
                SequenceFlow(id="flow_1", sourceId="start_1", targetId="timer_1"),
                SequenceFlow(id="flow_2", sourceId="timer_1", targetId="timer_empty"),
                SequenceFlow(id="flow_3", sourceId="timer_empty", targetId="end_1"),
            ],
            dataObjects=[
                DataObject(id="do_invoice", name="Invoice PDF", isCollection=False)
            ]
        )
        layout = SugiyamaLayoutEngine(ir).compute_layout()
        serializer = BpmnXmlSerializer(ir, layout)
        xml_str = serializer.serialize()

        # 1. Check strict XSD validity
        errors = validate_bpmn(xml_str)
        self.assertEqual(errors, [], f"B2 XML failed XSD validation: {errors}")

        # 2. Check timer_1 has timeDuration and NO timeCycle
        self.assertIn("PT2H", xml_str)
        self.assertNotIn("timeCycle", xml_str)
        self.assertNotIn("R/PT1H", xml_str)

        # 3. Check DataObjects presence in XML and BPMNDI
        self.assertIn('dataObject id="DataObject_do_invoice"', xml_str)
        self.assertIn('dataObjectReference id="DataObjectRef_do_invoice"', xml_str)
        self.assertIn('bpmnElement="DataObjectRef_do_invoice"', xml_str)

        # 4. Check element child ordering in start_1
        root = ET.fromstring(xml_str)
        start_node = root.find(".//{http://www.omg.org/spec/BPMN/20100524/MODEL}startEvent")
        self.assertIsNotNone(start_node)
        child_tags = [child.tag.split("}")[-1] for child in start_node]
        # documentation must come before outgoing
        self.assertEqual(child_tags[0], "documentation")
        self.assertIn("outgoing", child_tags[1:])

    def test_b3_single_pool_merging_and_multi_pool(self):
        """B3 Proof: single_pool config merges pools; single_pool=False keeps distinct pools."""
        # 1. With single_pool = True
        config.single_pool = True
        ir_multi = ProcessIR(
            id="multi_proc",
            name="Multi Pool Test",
            pools=[
                Pool(id="pool_a", name="Sales Dept", lanes=[Lane(id="lane_a1", name="Rep")]),
                Pool(id="pool_b", name="Billing Dept", lanes=[Lane(id="lane_b1", name="Accountant")]),
            ],
            elements=[
                FlowNode(id="node_1", name="Enter Order", type="task", laneId="lane_a1"),
                FlowNode(id="node_2", name="Invoice", type="task", laneId="lane_b1"),
            ],
            flows=[
                SequenceFlow(id="flow_1", sourceId="node_1", targetId="node_2")
            ]
        )
        validator = ProcessValidator(ir_multi)
        repaired, _ = validator.validate_and_repair()

        self.assertEqual(len(repaired.pools), 1)
        self.assertEqual(len(repaired.pools[0].lanes), 2)

        # 2. With single_pool = False
        config.single_pool = False
        ir_multi_2 = ProcessIR(
            id="multi_proc_2",
            name="Multi Pool Preserve",
            pools=[
                Pool(id="pool_a", name="Sales Dept", lanes=[Lane(id="lane_a1", name="Rep")]),
                Pool(id="pool_b", name="Billing Dept", lanes=[Lane(id="lane_b1", name="Accountant")]),
            ],
            elements=[
                FlowNode(id="node_1", name="Enter Order", type="task", laneId="lane_a1"),
                FlowNode(id="node_2", name="Invoice", type="task", laneId="lane_b1"),
            ],
            flows=[
                SequenceFlow(id="flow_1", sourceId="node_1", targetId="node_2", type="message")
            ]
        )
        validator_2 = ProcessValidator(ir_multi_2)
        repaired_2, _ = validator_2.validate_and_repair()
        self.assertEqual(len(repaired_2.pools), 2)
        # Restore default
        config.single_pool = True

    def test_b4_validator_policy_auto_fix_vs_blocking_errors(self):
        """B4 Proof: Safe issues auto-fixed; unreachable nodes and unlabeled gateway branches block export."""
        # Process with:
        # 1. Invalid NCName ID: "123-bad id" -> auto-fixed
        # 2. Missing start and end event -> auto-fixed
        # 3. Unreachable isolated node -> ERROR (not auto-bridged), export_blocked=True
        # 4. Gateway with unlabeled outgoing branch -> ERROR (not auto-labeled), export_blocked=True
        ir = ProcessIR(
            id="proc_b4",
            name="Validator Policy Test",
            pools=[Pool(id="p1", name="Pool", lanes=[Lane(id="l1", name="Lane")])],
            elements=[
                FlowNode(id="123-bad id", name="Task A", type="task", laneId="l1"),
                FlowNode(id="gw1", name="Check Approval", type="exclusiveGateway", laneId="l1"),
                FlowNode(id="task_b", name="Approved Task", type="task", laneId="l1"),
                FlowNode(id="task_c", name="Rejected Task", type="task", laneId="l1"),
                FlowNode(id="isolated_task", name="Orphan Task", type="task", laneId="l1"),
            ],
            flows=[
                SequenceFlow(id="f1", sourceId="123-bad id", targetId="gw1"),
                SequenceFlow(id="f2", sourceId="gw1", targetId="task_b", condition="Approved"),
                SequenceFlow(id="f3", sourceId="gw1", targetId="task_c"), # Missing condition/label
            ]
        )

        validator = ProcessValidator(ir)
        repaired, issues = validator.validate_and_repair()

        self.assertTrue(validator.export_blocked, "Validator must set export_blocked=True when errors exist.")
        error_msgs = [i.message for i in issues if i.severity == "ERROR"]
        self.assertTrue(any("unreachable" in m.lower() or "isolated" in m.lower() for m in error_msgs))
        self.assertTrue(any("unlabeled" in m.lower() or "condition" in m.lower() for m in error_msgs))

        # Check that openQuestions contains the blocking issues
        self.assertTrue(len(repaired.openQuestions) >= 2)

        # Check that ID was sanitized
        self.assertTrue(self.ncname_pattern.match(repaired.elements[0].id))

    def test_b5_exporter_metadata_and_id_validity(self):
        """B5 Proof: Serializer outputs exporter="Process2BPMN", exporterVersion=VERSION and NCName IDs."""
        ir = ProcessIR(
            id="123_invalid_root_id",
            name="Exporter Metadata Test",
            pools=[Pool(id="1_pool", name="Pool", lanes=[Lane(id="1_lane", name="Lane")])],
            elements=[
                FlowNode(id="1_start", name="Start", type="startEvent", laneId="1_lane"),
                FlowNode(id="2_end", name="End", type="endEvent", laneId="1_lane"),
            ],
            flows=[
                SequenceFlow(id="1_flow", sourceId="1_start", targetId="2_end")
            ]
        )
        validator = ProcessValidator(ir)
        repaired, _ = validator.validate_and_repair()

        layout = SugiyamaLayoutEngine(repaired).compute_layout()
        serializer = BpmnXmlSerializer(repaired, layout)
        xml_str = serializer.serialize()

        root = ET.fromstring(xml_str)
        self.assertEqual(root.attrib.get("exporter"), "Process2BPMN")
        self.assertEqual(root.attrib.get("exporterVersion"), VERSION)

        # Ensure all IDs in the entire XML match NCName regex
        for elem in root.iter():
            elem_id = elem.attrib.get("id")
            if elem_id:
                self.assertTrue(
                    self.ncname_pattern.match(elem_id),
                    f"Element ID '{elem_id}' in tag '{elem.tag}' does not match NCName regex."
                )


if __name__ == "__main__":
    unittest.main()
