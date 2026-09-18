"""
Deterministic Sugiyama-Style BPMN 2.0 Auto-Layout Engine.
Computes horizontal swimlane bands, topological layering (DAG ranking),
node coordinate bounds (dc:Bounds), orthogonal edge routing (di:waypoint),
and non-overlapping labels.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Set, Optional, Any
from dataclasses import dataclass, field
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane


@dataclass
class Bounds:
    x: float
    y: float
    width: float
    height: float


@dataclass
class Waypoint:
    x: float
    y: float


@dataclass
class EdgeLayout:
    flow_id: str
    waypoints: List[Waypoint]
    label_bounds: Optional[Bounds] = None


@dataclass
class NodeLayout:
    element_id: str
    bounds: Bounds
    label_bounds: Optional[Bounds] = None


@dataclass
class LaneLayout:
    lane_id: str
    pool_id: str
    bounds: Bounds


@dataclass
class PoolLayout:
    pool_id: str
    bounds: Bounds
    lanes: List[LaneLayout] = field(default_factory=list)


@dataclass
class DiagramLayout:
    pools: List[PoolLayout] = field(default_factory=list)
    nodes: Dict[str, NodeLayout] = field(default_factory=dict)
    edges: Dict[str, EdgeLayout] = field(default_factory=dict)
    total_width: float = 1200.0
    total_height: float = 600.0


def get_default_element_dimensions(elem_type: str) -> Tuple[float, float]:
    """Returns standard BPMN 2.0 dimensions (width, height) for element types."""
    lower = elem_type.lower()
    if "event" in lower:
        return 36.0, 36.0
    elif "gateway" in lower:
        return 50.0, 50.0
    elif "subprocess" in lower:
        return 140.0, 90.0
    elif "callactivity" in lower:
        return 120.0, 80.0
    else:  # tasks: task, userTask, serviceTask, manualTask, sendTask, receiveTask
        return 100.0, 80.0


class SugiyamaLayoutEngine:
    """
    Implements layered horizontal DAG auto-layout with orthogonal routing.
    """

    def __init__(
        self,
        ir: ProcessIR,
        start_x: float = 180.0,
        start_y: float = 80.0,
        lane_min_height: float = 180.0,
        x_gap: float = 80.0,
        y_gap: float = 30.0,
        template_spec: Optional[Any] = None,
    ):
        self.ir = ir
        self.start_x = start_x
        self.start_y = start_y
        self.lane_min_height = lane_min_height
        self.x_gap = x_gap
        self.y_gap = y_gap
        self.template_spec = template_spec
        if template_spec and hasattr(template_spec, "layout_metrics"):
            m = template_spec.layout_metrics
            self.lane_min_height = getattr(m, "default_lane_height", lane_min_height)
            self.x_gap = getattr(m, "horizontal_spacing", x_gap)
            self.y_gap = getattr(m, "vertical_spacing", y_gap)

    def compute_layout(self) -> DiagramLayout:
        layout = DiagramLayout()

        # 1. Topological Ranking of Flow Nodes
        ranks = self._compute_ranks()

        # 2. Group nodes by lane
        lane_to_nodes: Dict[str, List[FlowNode]] = {}
        for elem in self.ir.elements:
            lane_to_nodes.setdefault(elem.laneId, []).append(elem)

        # 3. Determine Lane & Pool dimensions
        curr_y = self.start_y
        max_col_rank = max(ranks.values()) if ranks else 0
        
        # Estimate pool width based on max rank
        estimated_content_width = (max_col_rank + 2) * (100.0 + self.x_gap) + 200.0
        pool_width = max(1100.0, estimated_content_width)

        for pool in self.ir.pools:
            pool_top_y = curr_y
            pool_layout = PoolLayout(
                pool_id=pool.id,
                bounds=Bounds(x=self.start_x - 40.0, y=curr_y, width=pool_width, height=0)
            )

            for lane in pool.lanes:
                lane_nodes = lane_to_nodes.get(lane.id, [])
                
                # Check how many parallel rows we need in this lane
                rank_counts: Dict[int, int] = {}
                for n in lane_nodes:
                    r = ranks.get(n.id, 0)
                    rank_counts[r] = rank_counts.get(r, 0) + 1
                max_in_one_col = max(rank_counts.values()) if rank_counts else 1
                
                lane_h = max(self.lane_min_height, max_in_one_col * (80.0 + self.y_gap) + 60.0)

                lane_layout = LaneLayout(
                    lane_id=lane.id,
                    pool_id=pool.id,
                    bounds=Bounds(
                        x=self.start_x - 10.0,
                        y=curr_y,
                        width=pool_width - 30.0,
                        height=lane_h
                    )
                )
                pool_layout.lanes.append(lane_layout)

                # Layout nodes inside this lane
                self._layout_lane_nodes(lane_nodes, lane_layout.bounds, ranks, layout)
                curr_y += lane_h

            pool_layout.bounds.height = curr_y - pool_top_y
            layout.pools.append(pool_layout)
            curr_y += 40.0  # Spacing between pools if multiple

        layout.total_width = pool_width + 100.0
        layout.total_height = curr_y + 100.0

        # Optional TemplateSpec hook: preserve fixed skeleton nodes
        if self.template_spec and hasattr(self.template_spec, "skeleton_nodes"):
            for sk in self.template_spec.skeleton_nodes:
                if getattr(sk, "is_fixed", False) and getattr(sk, "bounds", None) and sk.id not in layout.nodes:
                    b = sk.bounds
                    layout.nodes[sk.id] = NodeLayout(
                        element_id=sk.id,
                        bounds=Bounds(
                            x=float(b.get("x", 180.0)),
                            y=float(b.get("y", 150.0)),
                            width=float(b.get("width", 36.0)),
                            height=float(b.get("height", 36.0))
                        )
                    )

        # Position DataObjects
        for idx, do in enumerate(getattr(self.ir, "dataObjects", [])):
            do_ref_id = f"DataObjectRef_{do.id}"
            do_x = self.start_x + 40.0 + (idx * 90.0)
            do_y = self.start_y + 15.0
            layout.nodes[do_ref_id] = NodeLayout(
                element_id=do_ref_id,
                bounds=Bounds(x=do_x, y=do_y, width=36.0, height=50.0),
                label_bounds=Bounds(x=do_x - 10.0, y=do_y + 52.0, width=56.0, height=14.0)
            )

        # 4. Orthogonal Sequence Flow Routing
        self._route_edges(layout)

        return layout

    def _compute_ranks(self) -> Dict[str, int]:
        """Assigns horizontal rank (0..N) using DAG topological ordering."""
        elements_map = {e.id: e for e in self.ir.elements}
        ranks: Dict[str, int] = {}

        # Build adjacency
        out_edges: Dict[str, List[str]] = {e.id: [] for e in self.ir.elements}
        in_degree: Dict[str, int] = {e.id: 0 for e in self.ir.elements}

        for f in self.ir.flows:
            if f.sourceId in out_edges and f.targetId in out_edges:
                out_edges[f.sourceId].append(f.targetId)
                in_degree[f.targetId] += 1

        # Sources (start events or in_degree == 0)
        queue: List[str] = [eid for eid, deg in in_degree.items() if deg == 0]
        if not queue:
            # Cycle fallback
            starts = [e.id for e in self.ir.elements if e.type == "startEvent"]
            queue = starts if starts else ([self.ir.elements[0].id] if self.ir.elements else [])

        for q in queue:
            ranks[q] = 0

        visited: Set[str] = set()
        while queue:
            curr = queue.pop(0)
            visited.add(curr)
            curr_rank = ranks.get(curr, 0)

            for nxt in out_edges.get(curr, []):
                # Only increment rank if moving forward
                ranks[nxt] = max(ranks.get(nxt, 0), curr_rank + 1)
                if nxt not in visited and nxt not in queue:
                    queue.append(nxt)

        # Fallback for any unvisited nodes
        for e in self.ir.elements:
            if e.id not in ranks:
                ranks[e.id] = max(ranks.values()) + 1 if ranks else 0

        return ranks

    def _layout_lane_nodes(
        self,
        nodes: List[FlowNode],
        lane_bounds: Bounds,
        ranks: Dict[str, int],
        layout: DiagramLayout
    ) -> None:
        """Places nodes belonging to a single lane horizontally and centered vertically."""
        # Group nodes by rank
        by_rank: Dict[int, List[FlowNode]] = {}
        for n in nodes:
            r = ranks.get(n.id, 0)
            by_rank.setdefault(r, []).append(n)

        lane_center_y = lane_bounds.y + (lane_bounds.height / 2.0)

        for r, rank_nodes in by_rank.items():
            # X coordinate proportional to rank
            base_x = self.start_x + 40.0 + (r * (100.0 + self.x_gap))
            
            num_nodes = len(rank_nodes)
            for idx, node in enumerate(rank_nodes):
                w, h = get_default_element_dimensions(node.type)
                
                # Center vertically around lane centerline
                if num_nodes == 1:
                    node_y = lane_center_y - (h / 2.0)
                else:
                    offset = (idx - (num_nodes - 1) / 2.0) * (h + self.y_gap)
                    node_y = lane_center_y - (h / 2.0) + offset

                node_bounds = Bounds(x=base_x, y=node_y, width=w, height=h)

                # BPMNLabel bounds for events and gateways
                label_bounds: Optional[Bounds] = None
                lower_type = node.type.lower()
                if "event" in lower_type:
                    label_bounds = Bounds(
                        x=base_x - 25.0,
                        y=node_y + h + 6.0,
                        width=w + 50.0,
                        height=24.0
                    )
                elif "gateway" in lower_type:
                    label_bounds = Bounds(
                        x=base_x - 20.0,
                        y=node_y - 24.0,
                        width=w + 40.0,
                        height=20.0
                    )

                layout.nodes[node.id] = NodeLayout(
                    element_id=node.id,
                    bounds=node_bounds,
                    label_bounds=label_bounds
                )

    def _route_edges(self, layout: DiagramLayout) -> None:
        """Generates clean orthogonal Manhattan waypoints for every sequence flow."""
        for flow in self.ir.flows:
            source_layout = layout.nodes.get(flow.sourceId)
            target_layout = layout.nodes.get(flow.targetId)

            if not source_layout or not target_layout:
                continue

            sb = source_layout.bounds
            tb = target_layout.bounds

            s_center_x = sb.x + sb.width / 2.0
            s_center_y = sb.y + sb.height / 2.0
            t_center_x = tb.x + tb.width / 2.0
            t_center_y = tb.y + tb.height / 2.0

            waypoints: List[Waypoint] = []
            label_bounds: Optional[Bounds] = None

            # Case 1: Normal Forward Flow (source is to the left of target)
            if sb.x + sb.width < tb.x:
                start_pt = Waypoint(x=sb.x + sb.width, y=s_center_y)
                end_pt = Waypoint(x=tb.x, y=t_center_y)

                # Same horizontal row (within 6px)
                if abs(s_center_y - t_center_y) < 6.0:
                    waypoints = [start_pt, end_pt]
                    mid_x = (start_pt.x + end_pt.x) / 2.0
                    mid_y = s_center_y
                else:
                    # Orthogonal Z / S step
                    mid_x = (start_pt.x + end_pt.x) / 2.0
                    waypoints = [
                        start_pt,
                        Waypoint(x=mid_x, y=s_center_y),
                        Waypoint(x=mid_x, y=t_center_y),
                        end_pt
                    ]
                    mid_y = (s_center_y + t_center_y) / 2.0

                if flow.name or flow.condition:
                    disp_text = flow.name or flow.condition
                    label_bounds = Bounds(
                        x=mid_x - 30.0,
                        y=min(s_center_y, t_center_y) - 18.0,
                        width=max(60.0, len(disp_text) * 7.0),
                        height=16.0
                    )

            # Case 2: Backward Loop / Return Flow (source is ahead or equal to target)
            else:
                # Route bottom around nodes
                start_pt = Waypoint(x=s_center_x, y=sb.y + sb.height)
                end_pt = Waypoint(x=t_center_x, y=tb.y + tb.height)
                bottom_y = max(sb.y + sb.height, tb.y + tb.height) + 35.0

                waypoints = [
                    start_pt,
                    Waypoint(x=s_center_x, y=bottom_y),
                    Waypoint(x=t_center_x, y=bottom_y),
                    end_pt
                ]
                if flow.name or flow.condition:
                    disp_text = flow.name or flow.condition
                    label_bounds = Bounds(
                        x=(s_center_x + t_center_x) / 2.0 - 30.0,
                        y=bottom_y + 4.0,
                        width=max(60.0, len(disp_text) * 7.0),
                        height=16.0
                    )

            layout.edges[flow.id] = EdgeLayout(
                flow_id=flow.id,
                waypoints=waypoints,
                label_bounds=label_bounds
            )
