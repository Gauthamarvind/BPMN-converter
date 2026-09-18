"""
Unit test suite for Phase 1:
- ProcessIR data models
- Deterministic validator & graph repair
- Sugiyama auto-layout coordinates & orthogonal waypoints
- BPMN 2.0 XML + BPMNDI serialization
- Profile linter
"""

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane, SourceRef
from backend.pipeline.validator import ProcessValidator, sanitize_ncname
from backend.pipeline.layout import SugiyamaLayoutEngine
from backend.pipeline.serializer import BpmnXmlSerializer
from backend.pipeline.linter import ProfileLinter


class TestPhase1(unittest.TestCase):

    def setUp(self):
        self.lane1 = Lane(id="Lane_1", name="Finance Specialist")
        self.lane2 = Lane(id="Lane_2", name="Automated Bot")
        self.pool = Pool(id="Participant_1", name="Payment Organization", lanes=[self.lane1, self.lane2])

        self.start = FlowNode(id="Start_1", type="startEvent", name="Start Invoice", laneId="Lane_1")
        self.task1 = FlowNode(id="Task_1", type="userTask", name="Enter Invoice Details", laneId="Lane_1")
        self.gw = FlowNode(id="Gateway_1", type="exclusiveGateway", name="Check Amount", laneId="Lane_1")
        self.task2 = FlowNode(id="Task_2", type="serviceTask", name="Auto-Process Payment", laneId="Lane_2")
        self.task3 = FlowNode(id="Task_3", type="userTask", name="Manual Audit", laneId="Lane_1")
        self.end = FlowNode(id="End_1", type="endEvent", name="Payment Finished", laneId="Lane_1")

        self.flows = [
            SequenceFlow(id="Flow_1", sourceId="Start_1", targetId="Task_1"),
            SequenceFlow(id="Flow_2", sourceId="Task_1", targetId="Gateway_1"),
            SequenceFlow(id="Flow_3", sourceId="Gateway_1", targetId="Task_2", name="< $500", condition="Amount < 500"),
            SequenceFlow(id="Flow_4", sourceId="Gateway_1", targetId="Task_3", name=">= $500", condition="Amount >= 500"),
            SequenceFlow(id="Flow_5", sourceId="Task_2", targetId="End_1"),
            SequenceFlow(id="Flow_6", sourceId="Task_3", targetId="End_1"),
        ]

        self.ir = ProcessIR(
            id="InvoiceProcess",
            name="Invoice Processing",
            pools=[self.pool],
            elements=[self.start, self.task1, self.gw, self.task2, self.task3, self.end],
            flows=self.flows
        )

    def test_ncname_sanitizer(self):
        self.assertEqual(sanitize_ncname("123-Invalid!ID"), "id_123-Invalid_ID")
        self.assertEqual(sanitize_ncname("Valid_Name-1"), "Valid_Name-1")
        self.assertEqual(sanitize_ncname(" space name "), "space_name")
        self.assertTrue(sanitize_ncname("!@#").startswith("id_"))

    def test_validator_and_repair(self):
        # Create an IR missing a start event and containing an unreachable dangling node
        broken_ir = ProcessIR(
            id="Bad ID with spaces",
            elements=[
                FlowNode(id="Task_orphan", type="task", name="Isolated Activity", laneId=""),
                FlowNode(id="Task_mid", type="task", name="Middle Activity", laneId="Lane_1")
            ],
            flows=[]
        )

        validator = ProcessValidator(broken_ir)
        repaired, issues = validator.validate_and_repair()

        # Check process ID was sanitized
        self.assertNotIn(" ", repaired.id)
        # Check start event and end event were created
        has_start = any(e.type == "startEvent" for e in repaired.elements)
        has_end = any(e.type == "endEvent" for e in repaired.elements)
        self.assertTrue(has_start, "Validator must add missing startEvent")
        self.assertTrue(has_end, "Validator must add missing endEvent")
        # Check lane assignment
        for e in repaired.elements:
            self.assertTrue(bool(e.laneId), "Every element must be assigned to a valid lane")

    def test_sugiyama_layout(self):
        validator = ProcessValidator(self.ir)
        repaired, _ = validator.validate_and_repair()

        engine = SugiyamaLayoutEngine(repaired)
        layout = engine.compute_layout()

        # Pool bounds
        self.assertEqual(len(layout.pools), 1)
        pool = layout.pools[0]
        self.assertEqual(len(pool.lanes), 2)
        self.assertGreater(pool.bounds.width, 500)
        self.assertGreater(pool.bounds.height, 200)

        # Node coordinates
        for elem in repaired.elements:
            self.assertIn(elem.id, layout.nodes)
            node_layout = layout.nodes[elem.id]
            self.assertGreater(node_layout.bounds.width, 0)
            self.assertGreater(node_layout.bounds.height, 0)

        # Topological ordering check: Task_1 should be to the left of Gateway_1
        self.assertLess(
            layout.nodes["Task_1"].bounds.x,
            layout.nodes["Gateway_1"].bounds.x,
            "Predecessor should be to the left of successor"
        )

        # Orthogonal waypoints
        for flow in repaired.flows:
            self.assertIn(flow.id, layout.edges)
            edge = layout.edges[flow.id]
            self.assertGreaterEqual(len(edge.waypoints), 2, "Edge must have at least 2 waypoints")

    def test_bpmn_xml_serialization(self):
        engine = SugiyamaLayoutEngine(self.ir)
        layout = engine.compute_layout()

        serializer = BpmnXmlSerializer(self.ir, layout)
        xml_str = serializer.serialize()

        # Parse XML to guarantee well-formedness
        root = ET.fromstring(xml_str)
        self.assertTrue(root.tag.endswith("definitions"))

        # Check collaboration and process
        has_collab = any("collaboration" in el.tag for el in root)
        has_process = any("process" in el.tag for el in root)
        has_diagram = any("BPMNDiagram" in el.tag for el in root)
        self.assertTrue(has_collab, "Must contain collaboration")
        self.assertTrue(has_process, "Must contain process")
        self.assertTrue(has_diagram, "Must contain BPMNDiagram with BPMNDI")

    def test_profile_linter(self):
        linter = ProfileLinter()
        profiles = linter.list_available_profiles()
        self.assertIn("generic", profiles)
        self.assertIn("signavio", profiles)
        self.assertIn("camunda", profiles)

        result = linter.lint(self.ir, profile_name="signavio")
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.assumptions), 0)


if __name__ == "__main__":
    unittest.main()
