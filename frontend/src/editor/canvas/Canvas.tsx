import {
  Background, BackgroundVariant, Controls, MiniMap, ReactFlow, useReactFlow,
  type Connection, type Edge, type EdgeChange, type NodeChange, type OnDelete,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import type { SlotInstance } from "../../api/dynamic";
import { useCatalogStore } from "../../store/catalogStore";
import { useComponentStore, useCurrentSession, useRuntimePrefix } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";
import { componentIdOf, portsOfNode } from "../../lib/components";
import { probeMarkers } from "../../lib/probeRules";
import { scoped } from "../../lib/scope";
import { scriptMarkers } from "../../lib/scripts";
import { discardedEdges } from "../../lib/selectors";
import { hasWorker, isActive, type LiveProps } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore } from "../../store/uiStore";
import { useValidationStore } from "../../store/validationStore";
import { enterInstance } from "../blocks/componentActions";
import { ScopeBar } from "../blocks/ScopeBar";
import { deleteSelection } from "../selectionActions";
import { ELEMENT_MIME } from "../palette/PaletteItem";
import { addSlotAt } from "../slots/slotActions";
import { slotIdOf, slotLinkEdges, toSlotEdges, toSlotNodes, type SlotFlowNode } from "../slots/slotFlow";
import { SlotNode } from "../slots/SlotNode";
import { ConnectionLine } from "./ConnectionLine";
import { ElementNode } from "./ElementNode";
import { FlowEdge } from "./FlowEdge";
import { toFlowEdges, toFlowNodes, type ElementFlowNode, type PipelineFlowEdge } from "./toFlow";
import { useConnect } from "./useConnect";
import { applySelection } from "./selection";
import { ADVANCED } from "../../lib/features";
import { nodePerf, threadOfEdge, threadsInfo } from "../../lib/perf";

type CanvasNode = ElementFlowNode | SlotFlowNode;
type CanvasEdge = PipelineFlowEdge | Edge;

const nodeTypes = { element: ElementNode, slot: SlotNode };
const edgeTypes = { flow: FlowEdge };
const SNAP: [number, number] = [10, 10];
const FIT = { maxZoom: 1.1, padding: 0.06 };
const NO_LIVE_PROPS: LiveProps = {};
const NO_INSTANCES: Record<string, SlotInstance[]> = {};
const NOTHING = {};

export function Canvas() {
  const flow = useReactFlow<CanvasNode, CanvasEdge>();
  const graph = useGraphStore((s) => s.graph);
  const byName = useCatalogStore((s) => s.byName);
  const session = useCurrentSession();
  // Runtime ids inside an instance are "<instance>/<inner id>"; a library definition has none.
  const prefix = useRuntimePrefix();
  const nodeSeverities = useValidationStore((s) => s.byNode);
  const edgeSeverities = useValidationStore((s) => s.byEdge);
  const rawAlerts = useRuntimeStore((s) => s.nodeAlerts);
  const rawEdgeAlerts = useRuntimeStore((s) => s.edgeAlerts);
  const rawStats = useRuntimeStore((s) => s.stats);
  const rawCaps = useRuntimeStore((s) => s.caps);
  const running = useRuntimeStore((s) => isActive(s.state)) && prefix !== null;
  // Live values only describe a pipeline that still exists.
  const rawLiveProps = useRuntimeStore((s) => (hasWorker(s.state) ? s.liveProps : NO_LIVE_PROPS));
  const rawPending = useRuntimeStore((s) => (hasWorker(s.state) ? s.pending : NO_LIVE_PROPS));
  const live = useRuntimeStore((s) => (isActive(s.state) ? s.instances : NO_INSTANCES));
  const scope = useCallback(<T,>(record: Record<string, T>): Record<string, T> =>
    (prefix === null ? NOTHING : scoped(record, prefix)), [prefix]);
  const alerts = useMemo(() => scope(rawAlerts), [scope, rawAlerts]);
  const edgeAlerts = useMemo(() => scope(rawEdgeAlerts), [scope, rawEdgeAlerts]);
  const stats = useMemo(() => (rawStats ? { ...rawStats, edges: scope(rawStats.edges) } : null), [scope, rawStats]);
  const perf = useMemo(
    () => (running && rawStats ? nodePerf(graph, scope(rawStats.elements ?? {}), scope(rawStats.queues ?? {})) : undefined),
    [running, rawStats, graph, scope],
  );
  const edgeThreads = useMemo(() => scope(threadOfEdge(threadsInfo(rawStats?.threads))), [scope, rawStats]);
  const caps = useMemo(() => scope(rawCaps), [scope, rawCaps]);
  const liveProps = useMemo(() => scope(rawLiveProps), [scope, rawLiveProps]);
  const pending = useMemo(() => scope(rawPending), [scope, rawPending]);
  const markers = useMemo(() => scriptMarkers(graph), [graph]);
  const probes = useMemo(() => probeMarkers(graph), [graph]);
  const ports = useMemo(() => {
    if (!session) return undefined;
    return Object.fromEntries(graph.nodes.map((node) => [node.id, portsOfNode(session.ports, node.id)]));
  }, [session, graph.nodes]);
  const [slotDrag, setSlotDrag] = useState<Record<string, { x: number; y: number }>>({});
  const selectedNodes = useUiStore((s) => s.selectedNodes);
  const selectedEdges = useUiStore((s) => s.selectedEdges);
  const focusNode = useUiStore((s) => s.focusNode);
  const fitRequest = useUiStore((s) => s.fitRequest);
  const fitted = useRef(false);
  const measured = useRef<Record<string, { width: number; height: number }>>({});
  const [measureVersion, setMeasureVersion] = useState(0);
  const onConnect = useConnect();

  const nodes = useMemo<CanvasNode[]>(
    () => [
      ...toFlowNodes(graph, {
        byName, severities: nodeSeverities, alerts, selected: new Set(selectedNodes), measured: measured.current, liveProps,
        pending, markers, probeMarkers: probes, ports, extraEdges: slotLinkEdges(graph, byName), perf,
      }),
      ...toSlotNodes(graph, {
        byName, live: scope(live), running, selected: new Set(selectedNodes), positions: slotDrag, severities: nodeSeverities,
        stats: stats?.edges,
      }),
    ],
    // measureVersion invalidates the memo when node sizes change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [graph, byName, nodeSeverities, alerts, selectedNodes, measureVersion, liveProps, pending, markers, probes, ports,
      live, running, slotDrag, scope, stats, perf],
  );
  const discarded = useMemo(() => discardedEdges(graph, byName, liveProps), [graph, byName, liveProps]);
  const edges = useMemo<CanvasEdge[]>(
    () => [
      ...toFlowEdges(graph, {
        severities: edgeSeverities, stats: stats?.edges ?? {}, caps, selected: new Set(selectedEdges), running, discarded,
        alerts: edgeAlerts, markers, probeMarkers: probes, threads: edgeThreads,
      }),
      ...toSlotEdges(graph, byName),
    ],
    [graph, byName, edgeSeverities, stats, caps, selectedEdges, running, discarded, edgeAlerts, markers, probes, edgeThreads],
  );

  const onNodesChange = useCallback((changes: NodeChange<CanvasNode>[]) => {
    const positions: Record<string, { x: number; y: number }> = {};
    const slotPositions: Record<string, { x: number; y: number }> = {};
    let resized = false;
    for (const change of changes) {
      if (change.type === "position" && change.position) {
        if (slotIdOf(change.id)) slotPositions[change.id] = change.position;
        else positions[change.id] = change.position;
      }
      if (change.type === "dimensions" && change.dimensions) {
        measured.current[change.id] = change.dimensions;
        resized = true;
      }
    }
    if (Object.keys(positions).length) useGraphStore.getState().moveNodes(positions);
    if (Object.keys(slotPositions).length) setSlotDrag((current) => ({ ...current, ...slotPositions }));
    if (resized) setMeasureVersion((v) => v + 1);
    const ui = useUiStore.getState();
    const next = applySelection(ui.selectedNodes, changes);
    if (next !== ui.selectedNodes) ui.select(next, ui.selectedEdges);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange<CanvasEdge>[]) => {
    const ui = useUiStore.getState();
    const next = applySelection(ui.selectedEdges, changes);
    if (next !== ui.selectedEdges) ui.select(ui.selectedNodes, next);
  }, []);

  const onDelete: OnDelete<CanvasNode, CanvasEdge> = useCallback(({ nodes: gone, edges: cut }) => {
    deleteSelection(gone.map((n) => n.id), cut.filter((e) => e.type !== "default").map((e) => e.id));
  }, []);

  const onDrop = useCallback((event: DragEvent) => {
    const factory = event.dataTransfer.getData(ELEMENT_MIME);
    if (!factory) return;
    event.preventDefault();
    const position = flow.screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const component = componentIdOf(factory);
    // Alt/Shift-drop of a component: a slot of dynamic instances instead of one instance.
    if (ADVANCED && component && (event.altKey || event.shiftKey) && !useComponentStore.getState().sessions.length) {
      addSlotAt(component, { x: position.x - 90, y: position.y - 30 });
      return;
    }
    const node = useGraphStore.getState().addNode(factory, { x: position.x - 90, y: position.y - 30 });
    useUiStore.getState().select([node.id], []);
  }, [flow]);

  // Fit the graph once every node has been measured, then whenever asked to.
  useEffect(() => {
    if (fitted.current || graph.nodes.length === 0) return;
    if (!graph.nodes.every((node) => measured.current[node.id])) return;
    fitted.current = true;
    requestAnimationFrame(() => void flow.fitView(FIT));
  }, [measureVersion, graph.nodes, flow]);

  useEffect(() => {
    if (fitRequest === 0) return undefined;
    const timer = setTimeout(() => void flow.fitView({ ...FIT, duration: 300 }), 60);
    return () => clearTimeout(timer);
  }, [fitRequest, flow]);

  useEffect(() => {
    if (!focusNode) return;
    void flow.fitView({ nodes: [{ id: focusNode }], duration: 300, maxZoom: 1.3, padding: 0.5 });
    useUiStore.getState().requestFocus(null);
  }, [focusNode, flow]);

  const isValidConnection = useCallback(
    (connection: Connection | CanvasEdge) => connection.source !== connection.target
      && !slotIdOf(connection.source) && !slotIdOf(connection.target),
    [],
  );

  return (
    <div className="canvas" onDragOver={(event) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
    }} onDrop={onDrop}>
      <ScopeBar />
      <ReactFlow<CanvasNode, CanvasEdge>
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStart={(_event, node) => !slotIdOf(node.id) && useGraphStore.getState().checkpoint()}
        onNodeDragStop={(_event, _node, dragged) => {
          const dropped = dragged.filter((node) => slotIdOf(node.id));
          for (const node of dropped) {
            useGraphStore.getState().updateSlot(slotIdOf(node.id)!, { position: node.position });
          }
          // The graph is now the source of truth (undo moves the slot back).
          if (dropped.length) setSlotDrag({});
        }}
        onNodeDoubleClick={(_event, node) => {
          if (node.type === "element" && componentIdOf(node.data.node.factory)) void enterInstance(node.id);
        }}
        zoomOnDoubleClick={false}
        onConnect={onConnect}
        onDelete={onDelete}
        onEdgeMouseEnter={(_event, edge) => useUiStore.getState().hoverEdge(edge.id)}
        onEdgeMouseLeave={() => useUiStore.getState().hoverEdge(null)}
        isValidConnection={isValidConnection}
        connectionLineComponent={ConnectionLine}
        deleteKeyCode={["Delete", "Backspace"]}
        multiSelectionKeyCode={["Shift", "Meta", "Control"]}
        snapToGrid
        snapGrid={SNAP}
        minZoom={0.15}
        maxZoom={2.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.2} color="var(--canvas-dots)" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeStrokeWidth={2} className="minimap" />
      </ReactFlow>
      {graph.nodes.length === 0 && session ? (
        <div className="canvas-empty">
          <h3>Empty component</h3>
          <p>Add elements, then expose their free pads as ports and their properties as parameters (inspector).</p>
        </div>
      ) : null}
      {graph.nodes.length === 0 && !session && (graph.slots ?? []).length === 0 ? (
        <div className="canvas-empty">
          <h3>Start your pipeline</h3>
          <p>Drag elements from the palette on the left, or double-click them.</p>
          <p className="faint">Connect pads by dragging from an output (right) to an input (left). Pipelab checks
            caps compatibility and suggests converters, parsers and queues.</p>
        </div>
      ) : null}
    </div>
  );
}
