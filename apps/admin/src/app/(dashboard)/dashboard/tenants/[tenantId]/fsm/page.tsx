"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  useIntents,
  useCreateIntent,
  useUpdateIntent,
  useDeleteIntent,
  useActions,
  useTransitions,
  useReplaceTransitions,
} from "@/hooks/use-api";
import { createTraceEventSource } from "@/lib/api";
import type { FlowTransition, IntentDefinition, ActionCatalogItem } from "@/lib/api";
import { FSM_STATES, FSM_STATE_LABELS, FSM_STATE_COLORS, ACTION_COLORS, ACTION_LABELS, cn, type FSMStateKey } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Save,
  Plus,
  Trash2,
  Activity,
  GitBranch,
  Zap,
  Edit,
  Brain,
  Radio,
} from "lucide-react";
import { toast } from "sonner";
import { useSession } from "next-auth/react";

// ─── FSM state node layout grid ───────────────────────────────

const STATE_POSITIONS: Record<string, { x: number; y: number }> = {
  idle:            { x: 400, y: 20 },
  greeting:        { x: 400, y: 120 },
  discovery:       { x: 160, y: 240 },
  faq:             { x: 400, y: 240 },
  recommendation:  { x: 640, y: 240 },
  nps_survey:      { x: 160, y: 360 },
  complaint:       { x: 400, y: 360 },
  checkout:        { x: 640, y: 360 },
  handoff_pending: { x: 280, y: 480 },
  handoff_active:  { x: 520, y: 480 },
  escalation:      { x: 280, y: 580 },
  resolved:        { x: 520, y: 580 },
  closed:          { x: 400, y: 680 },
  error:           { x: 640, y: 680 },
};

// ─── Custom state node ─────────────────────────────────────────

function StateNode({
  data,
}: {
  data: { label: string; state: string; isActive: boolean; transitionCount: number };
}) {
  const colorClass = FSM_STATE_COLORS[data.state] ?? "bg-slate-100 border-slate-300 text-slate-700";
  return (
    <div
      className={cn(
        "rounded-xl border-2 px-4 py-2.5 min-w-[140px] text-center transition-all duration-300 shadow-sm",
        colorClass,
        data.isActive && "ring-4 ring-violet-500 ring-offset-2 scale-105 shadow-lg shadow-violet-200"
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0 !w-0 !h-0" />
      <div className="font-semibold text-xs uppercase tracking-wide">{data.label}</div>
      {data.transitionCount > 0 && (
        <div className="text-[10px] opacity-60 mt-0.5">{data.transitionCount} transitions</div>
      )}
      {data.isActive && (
        <div className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-violet-500 animate-pulse" />
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0 !w-0 !h-0" />
    </div>
  );
}

const nodeTypes: NodeTypes = { stateNode: StateNode };

// ─── Main page ─────────────────────────────────────────────────

export default function FSMPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;

  const { data: intentsData } = useIntents(tenantId);
  const { data: actionsData } = useActions(tenantId);
  const { data: transitionsData } = useTransitions(tenantId);
  const replaceTransitions = useReplaceTransitions(tenantId);

  const intents: IntentDefinition[] = intentsData?.data ?? [];
  const actions: ActionCatalogItem[] = actionsData?.data ?? [];
  const transitions: FlowTransition[] = transitionsData?.data ?? [];

  // Live trace state
  const [activeState, setActiveState] = useState<string | null>(null);
  const [traceEvents, setTraceEvents] = useState<any[]>([]);
  const [traceSessionId, setTraceSessionId] = useState("");
  const [traceConnected, setTraceConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // Editor state
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [editingTransition, setEditingTransition] = useState<Partial<FlowTransition> | null>(null);
  const [showIntentDialog, setShowIntentDialog] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Build React Flow nodes
  const transitionCountMap = useMemo(() => {
    const m: Record<string, number> = {};
    transitions.forEach((t) => {
      t.from_states.forEach((s) => {
        m[s] = (m[s] ?? 0) + 1;
      });
    });
    return m;
  }, [transitions]);

  const initialNodes: Node[] = useMemo(
    () =>
      Object.keys(STATE_POSITIONS).map((state) => ({
        id: state,
        type: "stateNode",
        position: STATE_POSITIONS[state],
        data: {
          label: FSM_STATE_LABELS[state] ?? state,
          state,
          isActive: activeState === state,
          transitionCount: transitionCountMap[state] ?? 0,
        },
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [transitionCountMap]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      transitions.flatMap((t, ti) =>
        t.from_states.map((fromState, si) => {
          const actionColor = ACTION_COLORS[t.action] ?? "#94a3b8";
          return {
            id: `e-${ti}-${si}`,
            source: fromState,
            target: t.to_state,
            label: `${t.intent ?? "*"} → ${ACTION_LABELS[t.action] ?? t.action}`,
            labelStyle: { fontSize: 10, fill: "#374151" },
            labelBgStyle: { fill: "white", fillOpacity: 0.85 },
            labelBgPadding: [4, 4] as [number, number],
            markerEnd: { type: MarkerType.ArrowClosed, color: actionColor },
            style: { stroke: actionColor, strokeWidth: 2 },
            data: { transition: t, fromState },
          };
        })
      ),
    [transitions]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync active node highlight into node data
  useEffect(() => {
    setNodes((ns) =>
      ns.map((n) => ({
        ...n,
        data: { ...n.data, isActive: activeState === n.id },
      }))
    );
  }, [activeState, setNodes]);

  // Sync new transitions into edges when fetched
  useEffect(() => {
    setEdges(initialEdges);
    setIsDirty(false);
  }, [initialEdges, setEdges]);

  // Sync new state positions into nodes when fetched
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  // ── Live trace ──────────────────────────────────────────────

  const startTrace = useCallback(() => {
    if (!traceSessionId.trim() || !token) return;
    esRef.current?.close();
    const es = createTraceEventSource(token, traceSessionId.trim());
    esRef.current = es;

    es.addEventListener("open", () => setTraceConnected(true));
    es.addEventListener("error", () => {
      setTraceConnected(false);
    });
    es.addEventListener("message", (evt) => {
      try {
        const event = JSON.parse(evt.data);
        setTraceEvents((prev: any[]) => [event, ...prev].slice(0, 50));
        if (event.type === "fsm_transition" && event.to) {
          setActiveState(event.to);
          setTimeout(() => setActiveState(null), 3000);
        }
        if (event.type === "intent_detected" && event.fsm_state) {
          setActiveState(event.fsm_state);
        }
      } catch {}
    });
  }, [traceSessionId, token]);

  const stopTrace = useCallback(() => {
    esRef.current?.close();
    setTraceConnected(false);
    setActiveState(null);
  }, []);

  useEffect(() => () => esRef.current?.close(), []);

  // ── Edge click → edit transition ───────────────────────────

  const onEdgeClick = useCallback(
    (_: MouseEvent, edge: Edge) => {
      setSelectedEdge(edge);
      setEditingTransition({ ...(edge.data?.transition ?? {}) });
    },
    []
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        ...connection,
        id: `e-new-${Date.now()}`,
        source: connection.source ?? "idle",
        target: connection.target ?? "idle",
        label: "new",
        markerEnd: { type: MarkerType.ArrowClosed },
        data: {
          transition: {
            from_states: [connection.source ?? "idle"],
            to_state: connection.target ?? "idle",
            intent: "",
            action: "faq",
            enabled: true,
          } satisfies FlowTransition,
          fromState: connection.source,
        },
      };
      setEdges((es) => addEdge(newEdge, es));
      setSelectedEdge(newEdge);
      setEditingTransition(newEdge.data?.transition);
      setIsDirty(true);
    },
    [setEdges]
  );

  const saveEdgeTransition = useCallback(() => {
    if (!selectedEdge || !editingTransition) return;
    setEdges((es) =>
      es.map((e) => {
        if (e.id !== selectedEdge.id) return e;
        const t = { ...e.data.transition, ...editingTransition } as FlowTransition;
        const actionColor = ACTION_COLORS[t.action] ?? "#94a3b8";
        return {
          ...e,
          label: `${t.intent ?? "*"} → ${ACTION_LABELS[t.action] ?? t.action}`,
          style: { stroke: actionColor, strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: actionColor },
          data: { transition: t },
        };
      })
    );
    setIsDirty(true);
    setSelectedEdge(null);
    setEditingTransition(null);
  }, [selectedEdge, editingTransition, setEdges]);

  const deleteEdge = useCallback(() => {
    if (!selectedEdge) return;
    setEdges((es) => es.filter((e) => e.id !== selectedEdge.id));
    setIsDirty(true);
    setSelectedEdge(null);
    setEditingTransition(null);
  }, [selectedEdge, setEdges]);

  // ── Save all transitions ────────────────────────────────────

  const saveAll = useCallback(async () => {
    const newTransitions: FlowTransition[] = edges.map((e) => e.data?.transition).filter(Boolean);
    try {
      await replaceTransitions.mutateAsync(newTransitions);
      setIsDirty(false);
      toast.success("FSM transitions saved");
    } catch {
      toast.error("Failed to save transitions");
    }
  }, [edges, replaceTransitions]);

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Main canvas ────────────────────────────────────── */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgeClick={onEdgeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          defaultEdgeOptions={{ animated: false }}
        >
          <Background gap={16} size={1} color="#e5e7eb" />
          <Controls />
          <MiniMap nodeColor={(n) => {
            const color = FSM_STATE_COLORS[n.data?.state ?? ""] ?? "";
            if (color.includes("blue")) return "#3b82f6";
            if (color.includes("green")) return "#22c55e";
            if (color.includes("amber")) return "#f59e0b";
            if (color.includes("red")) return "#ef4444";
            if (color.includes("purple")) return "#a855f7";
            return "#94a3b8";
          }} />
        </ReactFlow>

        {/* Canvas toolbar */}
        <div className="absolute top-4 left-4 flex gap-2 z-10">
          <Button
            size="sm"
            variant={isDirty ? "default" : "outline"}
            onClick={saveAll}
            loading={replaceTransitions.isPending}
            disabled={!isDirty}
          >
            <Save className="h-3.5 w-3.5 mr-1" />
            {isDirty ? "Save Changes" : "Saved"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowIntentDialog(true)}
          >
            <Brain className="h-3.5 w-3.5 mr-1" />
            Intents
          </Button>
        </div>

        {/* Drag hint */}
        <div className="absolute bottom-12 left-4 text-xs text-muted-foreground bg-white/80 px-2 py-1 rounded border z-10">
          Drag between nodes to add transition · Click an edge to edit
        </div>
      </div>

      {/* ── Right panel ────────────────────────────────────── */}
      <div className="w-80 border-l bg-background flex flex-col overflow-hidden">
        <Tabs defaultValue="editor" className="flex flex-col h-full">
          <TabsList className="m-3 mb-0">
            <TabsTrigger value="editor" className="flex-1">
              <GitBranch className="h-3.5 w-3.5 mr-1" />
              Editor
            </TabsTrigger>
            <TabsTrigger value="trace" className="flex-1">
              <Activity className="h-3.5 w-3.5 mr-1" />
              Live Trace
            </TabsTrigger>
          </TabsList>

          {/* ── Editor tab ─────────────────────────────────── */}
          <TabsContent value="editor" className="flex-1 overflow-y-auto p-3 space-y-4">
            {editingTransition ? (
              <TransitionEditor
                transition={editingTransition}
                intents={intents}
                actions={actions}
                onChange={setEditingTransition}
                onSave={saveEdgeTransition}
                onDelete={deleteEdge}
                onCancel={() => { setSelectedEdge(null); setEditingTransition(null); }}
              />
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Click on an edge to edit a transition, or drag from a node handle to create one.
                </p>
                <div className="space-y-2">
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Legend
                  </div>
                  {Object.entries(ACTION_LABELS).map(([action, label]) => (
                    <div key={action} className="flex items-center gap-2 text-xs">
                      <div
                        className="h-2 w-6 rounded-full"
                        style={{ backgroundColor: ACTION_COLORS[action] }}
                      />
                      <span>{label}</span>
                    </div>
                  ))}
                </div>
                <div className="pt-2 border-t space-y-1.5">
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Transitions ({edges.length})
                  </div>
                  {edges.map((e) => {
                    const t = e.data?.transition as FlowTransition | undefined;
                    if (!t) return null;
                    return (
                      <button
                        key={e.id}
                        onClick={() => { setSelectedEdge(e); setEditingTransition({ ...t }); }}
                        className="w-full text-left rounded-md border p-2 text-xs hover:bg-accent transition-colors"
                      >
                        <span className="font-medium">{FSM_STATE_LABELS[e.data?.fromState ?? ""] ?? e.data?.fromState}</span>
                        <span className="text-muted-foreground"> → </span>
                        <span className="font-medium">{FSM_STATE_LABELS[t.to_state] ?? t.to_state}</span>
                        <div className="text-muted-foreground mt-0.5">
                          {t.intent ?? "any intent"} · {ACTION_LABELS[t.action] ?? t.action}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </TabsContent>

          {/* ── Trace tab ──────────────────────────────────── */}
          <TabsContent value="trace" className="flex-1 flex flex-col overflow-hidden p-3 space-y-3">
            <div className="space-y-2">
              <Label className="text-xs">Session ID to trace</Label>
              <Input
                placeholder="session_abc123"
                value={traceSessionId}
                onChange={(e) => setTraceSessionId(e.target.value)}
                className="font-mono text-xs h-8"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="flex-1"
                  onClick={startTrace}
                  disabled={traceConnected || !traceSessionId.trim()}
                >
                  <Radio className="h-3.5 w-3.5 mr-1" />
                  {traceConnected ? "Connected" : "Connect"}
                </Button>
                {traceConnected && (
                  <Button size="sm" variant="outline" onClick={stopTrace}>
                    Stop
                  </Button>
                )}
              </div>
              {traceConnected && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  Streaming live trace events
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 text-xs">
              {traceEvents.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                  No events yet. Connect to a live session to see execution trace.
                </p>
              ) : (
                traceEvents.map((evt, i) => <TraceEventCard key={i} event={evt} />)
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* ── Intent manager dialog ─────────────────────────── */}
      <IntentManagerDialog
        tenantId={tenantId}
        open={showIntentDialog}
        onClose={() => setShowIntentDialog(false)}
        intents={intents}
      />
    </div>
  );
}

// ─── Transition editor ─────────────────────────────────────────

// When editing, we work with a single from/to state pair + the transition data.
// The FlowTransition.from_states[] is managed at save time.
interface EditingTransition {
  fromState: string;
  to_state: string;
  intent: string;
  action: string;
  static_message?: string;
  enabled: boolean;
  priority?: number;
}

function TransitionEditor({
  transition,
  intents,
  actions,
  onChange,
  onSave,
  onDelete,
  onCancel,
}: {
  transition: Partial<EditingTransition>;
  intents: IntentDefinition[];
  actions: ActionCatalogItem[];
  onChange: (t: Partial<EditingTransition>) => void;
  onSave: () => void;
  onDelete: () => void;
  onCancel: () => void;
}) {
  const ALL_STATES = Object.keys(STATE_POSITIONS);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm">Edit Transition</div>
        <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={onCancel}>
          Cancel
        </Button>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">From State</Label>
        <Select value={transition.fromState} onValueChange={(v) => onChange({ ...transition, fromState: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ALL_STATES.map((s) => (
              <SelectItem key={s} value={s} className="text-xs">
                {FSM_STATE_LABELS[s] ?? s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">To State</Label>
        <Select value={transition.to_state} onValueChange={(v) => onChange({ ...transition, to_state: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ALL_STATES.map((s) => (
              <SelectItem key={s} value={s} className="text-xs">
                {FSM_STATE_LABELS[s] ?? s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Intent <span className="text-muted-foreground">(leave blank for wildcard)</span></Label>
        <Select
          value={transition.intent ?? ""}
          onValueChange={(v) => onChange({ ...transition, intent: v })}
        >
          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Any intent" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="" className="text-xs text-muted-foreground">Any intent (wildcard)</SelectItem>
            {intents.map((i) => (
              <SelectItem key={i.key} value={i.key} className="text-xs">
                {i.name ?? i.key}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label className="text-xs">Action</Label>
        <Select
          value={transition.action}
          onValueChange={(v) => onChange({ ...transition, action: v })}
        >
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(actions.length > 0 ? actions.map((a) => a.key) : Object.keys(ACTION_LABELS)).map((a) => (
              <SelectItem key={a} value={a} className="text-xs">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: ACTION_COLORS[a] }} />
                  {ACTION_LABELS[a] ?? a}
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {transition.action === "static_reply" && (
        <div className="space-y-1.5">
          <Label className="text-xs">Static Message</Label>
          <Input
            className="text-xs h-8"
            placeholder="Message to send…"
            value={transition.static_message ?? ""}
            onChange={(e) => onChange({ ...transition, static_message: e.target.value })}
          />
        </div>
      )}

      <div className="space-y-1.5">
        <Label className="text-xs">Priority</Label>
        <Input
          type="number"
          className="text-xs h-8"
          value={transition.priority ?? 50}
          onChange={(e) => onChange({ ...transition, priority: Number(e.target.value) })}
        />
      </div>

      <div className="flex gap-2 pt-1">
        <Button size="sm" className="flex-1" onClick={onSave}>
          <Save className="h-3.5 w-3.5 mr-1" />
          Apply
        </Button>
        <Button size="sm" variant="destructive" onClick={onDelete}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ─── Trace event card ──────────────────────────────────────────

function TraceEventCard({ event }: { event: any }) {
  const typeColors: Record<string, string> = {
    intent_detected: "bg-blue-50 border-blue-200 text-blue-700",
    fsm_transition: "bg-violet-50 border-violet-200 text-violet-700",
    skill_call: "bg-emerald-50 border-emerald-200 text-emerald-700",
    connected: "bg-slate-50 border-slate-200 text-slate-500",
  };

  const icons: Record<string, React.ReactNode> = {
    intent_detected: <Brain className="h-3 w-3" />,
    fsm_transition: <GitBranch className="h-3 w-3" />,
    skill_call: <Zap className="h-3 w-3" />,
  };

  const colorClass = typeColors[event.type] ?? "bg-slate-50 border-slate-200";

  return (
    <div className={cn("rounded border p-2 font-mono", colorClass)}>
      <div className="flex items-center gap-1 font-medium mb-1">
        {icons[event.type]}
        <span>{event.type}</span>
      </div>
      {event.type === "intent_detected" && (
        <div className="text-[10px] space-y-0.5">
          <div>Intent: <strong>{event.intent}</strong></div>
          <div>Confidence: {(event.confidence * 100).toFixed(0)}%</div>
          <div>State: {event.fsm_state}</div>
        </div>
      )}
      {event.type === "fsm_transition" && (
        <div className="text-[10px] space-y-0.5">
          <div>→ <strong>{FSM_STATE_LABELS[event.to] ?? event.to}</strong></div>
          <div>Action: {ACTION_LABELS[event.action] ?? event.action}</div>
          {event.handoff && <div className="text-amber-600 font-semibold">Handoff triggered</div>}
        </div>
      )}
      {event.type === "skill_call" && (
        <div className="text-[10px] space-y-0.5">
          <div>Skill: <strong>{event.action}</strong></div>
          <div>Intent: {event.intent}</div>
        </div>
      )}
    </div>
  );
}

// ─── Intent manager dialog ─────────────────────────────────────

function IntentManagerDialog({
  tenantId,
  open,
  onClose,
  intents,
}: {
  tenantId: string;
  open: boolean;
  onClose: () => void;
  intents: IntentDefinition[];
}) {
  const createIntent = useCreateIntent(tenantId);
  const updateIntent = useUpdateIntent(tenantId);
  const deleteIntent = useDeleteIntent(tenantId);
  const [newName, setNewName] = useState("");
  const [newDisplay, setNewDisplay] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Partial<IntentDefinition>>({});

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await createIntent.mutateAsync({
      key: newName.trim(),
      name: newDisplay.trim() || newName.trim(),
      description: "",
      examples: [],
      enabled: true,
      priority: 50,
    });
    setNewName("");
    setNewDisplay("");
    toast.success("Intent created");
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Intents</DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          {/* Create new intent */}
          <div className="rounded-lg border p-3 space-y-2">
            <div className="text-xs font-medium text-muted-foreground uppercase">New Intent</div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Name (slug)</Label>
                <Input
                  className="h-8 text-xs font-mono"
                  placeholder="ask_price"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value.toLowerCase().replace(/\s+/g, "_"))}
                />
              </div>
              <div>
                <Label className="text-xs">Display Name</Label>
                <Input
                  className="h-8 text-xs"
                  placeholder="Ask about price"
                  value={newDisplay}
                  onChange={(e) => setNewDisplay(e.target.value)}
                />
              </div>
            </div>
            <Button
              size="sm"
              onClick={handleCreate}
              loading={createIntent.isPending}
              disabled={!newName.trim()}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Create Intent
            </Button>
          </div>

          {/* Intent list */}
          <div className="space-y-2">
            {intents.map((intent) => (
              <div key={intent.key} className="rounded-lg border p-3">
                {editingId === intent.key ? (
                  <div className="space-y-2">
                    <Input
                      className="h-8 text-xs"
                      value={editValues.name ?? intent.name}
                      onChange={(e: any) => setEditValues((v) => ({ ...v, name: e.target.value }))}
                    />
                    <Input
                      className="h-8 text-xs"
                      placeholder="Description"
                      value={editValues.description ?? intent.description}
                      onChange={(e: any) => setEditValues((v) => ({ ...v, description: e.target.value }))}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        className="h-7 text-xs"
                        loading={updateIntent.isPending}
                        onClick={async () => {
                          await updateIntent.mutateAsync({ key: intent.key, updates: editValues });
                          setEditingId(null);
                        }}
                      >
                        Save
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setEditingId(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium">{intent.name ?? intent.key}</div>
                      <div className="text-xs font-mono text-muted-foreground">{intent.key}</div>
                      {intent.description && (
                        <div className="text-xs text-muted-foreground mt-0.5">{intent.description}</div>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => { setEditingId(intent.key); setEditValues(intent); }}
                      >
                        <Edit className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive hover:text-destructive"
                        loading={deleteIntent.isPending}
                        onClick={() => deleteIntent.mutate(intent.key)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
