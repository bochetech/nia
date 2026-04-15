"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  ConnectionMode,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  type Viewport,
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
  useSkills,
  useFSMStates,
  useCreateFSMState,
  useDeleteFSMState,
} from "@/hooks/use-api";
import type { FlowTransition, IntentDefinition, ActionCatalogItem, SkillConfig } from "@/lib/api";
import { ACTION_COLORS, ACTION_LABELS, cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  Save,
  Plus,
  Trash2,
  GitBranch,
  Zap,
  Edit,
  Brain,
  Layers,
  HelpCircle,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useSession } from "next-auth/react";

// ─── FSM state layout ─────────────────────────────────────────
//
// ALL states are fetched dynamically from GET /{tenant_id}/states.
// Positions are saved to localStorage keyed by tenantId so layout persists.
// Only "idle" and the virtual "★ ANY" node are immutable.

/** Virtual node ID used to represent wildcard "from any state" transitions. */
const ANY_NODE_ID = "__any__";
const ANY_NODE_POSITION = { x: 20, y: 20 };

/** Auto-position states in a grid layout (fallback when no saved position). */
function autoPosition(index: number): { x: number; y: number } {
  const cols = 4;
  const col = index % cols;
  const row = Math.floor(index / cols);
  return { x: 80 + col * 220, y: 60 + row * 130 };
}

// ─── Layout persistence (localStorage) ───────────────────────

interface SavedLayout {
  positions: Record<string, { x: number; y: number }>;
  viewport: Viewport;
}

function layoutKey(tenantId: string) {
  return `nia_fsm_layout_${tenantId}`;
}

function loadLayout(tenantId: string): SavedLayout | null {
  try {
    const raw = localStorage.getItem(layoutKey(tenantId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveLayout(tenantId: string, positions: Record<string, { x: number; y: number }>, viewport: Viewport) {
  try {
    localStorage.setItem(layoutKey(tenantId), JSON.stringify({ positions, viewport }));
  } catch {
    // storage quota — ignore
  }
}

// Sentinel value used in the intent Select to represent "wildcard / no filter"
const INTENT_WILDCARD = "__wildcard__";
// Sentinel for "from any state" (from_states: [])
const FROM_ANY = "__any__";

/** Resolve an action key → display label. Handles conversational__ sub-skills. */
function actionLabel(action: string, customSkills?: { action: string; name?: string }[]): string {
  if (action.startsWith("conversational__")) {
    const skill = customSkills?.find((s) => s.action === action);
    if (skill?.name) return skill.name;
    return action.replace("conversational__", "").replace(/_/g, " ");
  }
  return ACTION_LABELS[action] ?? action;
}

// ─── Custom state node ─────────────────────────────────────────

/** Visible dot on each edge of a node for precise connection targeting (draw.io style). */
const HANDLE_DOT: React.CSSProperties = {
  width: 10,
  height: 10,
  background: "#818cf8",
  border: "2px solid #fff",
  borderRadius: "50%",
  boxShadow: "0 0 0 1px #818cf8",
  opacity: 0,
  transition: "opacity 0.15s",
};

const HANDLE_HOVER_CLASS =
  "group-hover/node:[&_.react-flow__handle]:opacity-100";

function StateNode({
  data,
}: {
  data: {
    label: string;
    state: string;
    isActive: boolean;
    transitionCount: number;
    isGhost?: boolean;
  };
}) {
  return (
    <div
      className={cn(
        "group/node rounded-xl border-2 px-4 py-3 min-w-[148px] text-center transition-all duration-300 relative",
        HANDLE_HOVER_CLASS,
        data.isGhost
          ? "bg-slate-50 border-dashed border-slate-300"
          : "bg-white",
        data.isActive
          ? "border-violet-500 scale-105 shadow-[0_0_0_4px_rgba(124,58,237,0.15),0_4px_16px_rgba(124,58,237,0.1)]"
          : data.isGhost
          ? ""
          : "border-slate-200 shadow-sm hover:shadow-md hover:border-violet-300"
      )}
    >
      {/* ── Source handles (outgoing) ── */}
      <Handle type="source" position={Position.Top}    id="s-top"    style={{ ...HANDLE_DOT, top: -5, left: "50%", transform: "translateX(-50%)" }} />
      <Handle type="source" position={Position.Bottom} id="s-bottom" style={{ ...HANDLE_DOT, bottom: -5, left: "50%", transform: "translateX(-50%)" }} />
      <Handle type="source" position={Position.Left}   id="s-left"   style={{ ...HANDLE_DOT, left: -5, top: "50%", transform: "translateY(-50%)" }} />
      <Handle type="source" position={Position.Right}  id="s-right"  style={{ ...HANDLE_DOT, right: -5, top: "50%", transform: "translateY(-50%)" }} />

      {/* ── Target handles (incoming) — small, inline with border ── */}
      <Handle type="target" position={Position.Top}    id="t-top"    style={{ ...HANDLE_DOT, background: "#34d399", boxShadow: "0 0 0 1px #34d399", top: -5, left: "35%", transform: "translateX(-50%)" }} />
      <Handle type="target" position={Position.Bottom} id="t-bottom" style={{ ...HANDLE_DOT, background: "#34d399", boxShadow: "0 0 0 1px #34d399", bottom: -5, left: "35%", transform: "translateX(-50%)" }} />
      <Handle type="target" position={Position.Left}   id="t-left"   style={{ ...HANDLE_DOT, background: "#34d399", boxShadow: "0 0 0 1px #34d399", left: -5, top: "35%", transform: "translateY(-50%)" }} />
      <Handle type="target" position={Position.Right}  id="t-right"  style={{ ...HANDLE_DOT, background: "#34d399", boxShadow: "0 0 0 1px #34d399", right: -5, top: "35%", transform: "translateY(-50%)" }} />

      <div className={cn("font-semibold text-[11px] uppercase tracking-wide", data.isGhost ? "text-slate-400" : "text-slate-700")}>
        {data.label}
      </div>

      {data.isGhost ? (
        <div className="text-[9px] text-slate-400 mt-0.5 italic">not in states list</div>
      ) : data.transitionCount > 0 ? (
        <div className="text-[10px] text-slate-400 mt-0.5">{data.transitionCount} transition{data.transitionCount !== 1 ? "s" : ""}</div>
      ) : null}

      {/* Active pulse indicator */}
      {data.isActive && (
        <div className="absolute -top-1.5 -right-1.5 h-3.5 w-3.5 rounded-full bg-[#007AFF] animate-pulse shadow-lg" />
      )}
    </div>
  );
}

const nodeTypes: NodeTypes = { stateNode: StateNode, anyNode: AnyStateNode };

// ─── Virtual "★ Any State" node ────────────────────────────────

function AnyStateNode() {
  return (
    <div className={cn("group/node rounded-xl border-2 border-dashed border-amber-400 bg-amber-50/80 px-5 py-3 min-w-[120px] text-center shadow-sm relative", HANDLE_HOVER_CLASS)}>
      <Handle type="source" position={Position.Top}    id="s-top"    style={{ ...HANDLE_DOT, top: -5, left: "50%", transform: "translateX(-50%)", background: "#f59e0b", boxShadow: "0 0 0 1px #f59e0b" }} />
      <Handle type="source" position={Position.Bottom} id="s-bottom" style={{ ...HANDLE_DOT, bottom: -5, left: "50%", transform: "translateX(-50%)", background: "#f59e0b", boxShadow: "0 0 0 1px #f59e0b" }} />
      <Handle type="source" position={Position.Left}   id="s-left"   style={{ ...HANDLE_DOT, left: -5, top: "50%", transform: "translateY(-50%)", background: "#f59e0b", boxShadow: "0 0 0 1px #f59e0b" }} />
      <Handle type="source" position={Position.Right}  id="s-right"  style={{ ...HANDLE_DOT, right: -5, top: "50%", transform: "translateY(-50%)", background: "#f59e0b", boxShadow: "0 0 0 1px #f59e0b" }} />
      <div className="font-semibold text-[12px] text-amber-700 tracking-wide">★ ANY STATE</div>
      <div className="text-[9px] text-amber-500 mt-0.5">wildcard source</div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────

export default function FSMPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  return (
    <ReactFlowProvider>
      <FSMCanvas tenantId={tenantId} />
    </ReactFlowProvider>
  );
}

function FSMCanvas({ tenantId }: { tenantId: string }) {
  const { data: session } = useSession();
  const token = (session as any)?.accessToken as string | undefined;
  const { setViewport } = useReactFlow();

  const { data: intentsData } = useIntents(tenantId);
  const { data: actionsData } = useActions(tenantId);
  const { data: transitionsData } = useTransitions(tenantId);
  const { data: skillsData } = useSkills(tenantId);
  const { data: statesData } = useFSMStates(tenantId);
  const replaceTransitions = useReplaceTransitions(tenantId);

  const intents: IntentDefinition[] = intentsData?.data ?? [];
  const actions: ActionCatalogItem[] = actionsData?.data ?? [];
  const transitions: FlowTransition[] = transitionsData?.data ?? [];
  // Custom conversational sub-skills (action key = "conversational__slug")
  const customSkills: SkillConfig[] = useMemo(
    () => (skillsData?.data ?? []).filter((s: SkillConfig) => s.action.startsWith("conversational__")),
    [skillsData]
  );

  // Dynamic state list from backend — while loading, show just "idle"
  const fsmStateItems: { key: string; label: string; is_default?: boolean }[] = useMemo(() => {
    if (statesData?.data?.length) return statesData.data;
    return [{ key: "idle", label: "Idle" }];
  }, [statesData]);

  // Collect ALL states referenced in transitions (to auto-create ghost nodes for unknown ones)
  const allReferencedStateKeys: string[] = useMemo(() => {
    const knownKeys = new Set(fsmStateItems.map((s) => s.key));
    const extra = new Set<string>();
    transitions.forEach((t) => {
      t.from_states.forEach((s) => { if (!knownKeys.has(s)) extra.add(s); });
      if (t.to_state && t.to_state !== "__same__" && !knownKeys.has(t.to_state)) extra.add(t.to_state);
    });
    return [...extra];
  }, [fsmStateItems, transitions]);

  // Combined state list: known states + ghost states for orphaned transition targets
  const allStateItems: { key: string; label: string; is_default?: boolean; isGhost?: boolean }[] = useMemo(() => {
    const ghost = allReferencedStateKeys.map((k) => ({
      key: k,
      label: k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      is_default: false,
      isGhost: true,
    }));
    return [...fsmStateItems, ...ghost];
  }, [fsmStateItems, allReferencedStateKeys]);

  // State label lookup: key → display name
  const FSM_STATE_LABELS_DYNAMIC: Record<string, string> = useMemo(
    () => Object.fromEntries(allStateItems.map((s) => [s.key, s.label])),
    [allStateItems]
  );

  // Position lookup: saved layout first, then auto-grid fallback
  const savedLayout = useMemo(() => loadLayout(tenantId), []); // eslint-disable-line react-hooks/exhaustive-deps

  const STATE_POSITIONS_DYNAMIC: Record<string, { x: number; y: number }> = useMemo(() => {
    return Object.fromEntries(
      allStateItems.map((s, i) => [
        s.key,
        savedLayout?.positions?.[s.key] ?? autoPosition(i),
      ])
    );
  }, [allStateItems, savedLayout]);

  // Live trace state (active state highlight only — no SSE panel in this page)
  const [activeState, setActiveState] = useState<string | null>(null);

  // Editor state
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [editingTransition, setEditingTransition] = useState<Partial<EditingTransition> | null>(null);
  const [showIntentDialog, setShowIntentDialog] = useState(false);
  const [showStatesDialog, setShowStatesDialog] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const pendingSaveRef = useRef(false);

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

  const hasWildcards = useMemo(
    () => transitions.some((t) => t.from_states.length === 0),
    [transitions]
  );

  const initialNodes: Node[] = useMemo(() => {
    const stateNodes = allStateItems.map((stateItem) => ({
      id: stateItem.key,
      type: "stateNode",
      position: STATE_POSITIONS_DYNAMIC[stateItem.key],
      data: {
        label: stateItem.label,
        state: stateItem.key,
        isActive: false,
        transitionCount: transitionCountMap[stateItem.key] ?? 0,
        isGhost: stateItem.isGhost ?? false,
      },
    }));

    // Add virtual ★ ANY node when there are wildcard transitions
    if (hasWildcards) {
      stateNodes.unshift({
        id: ANY_NODE_ID,
        type: "anyNode" as any,
        position: ANY_NODE_POSITION,
        data: { label: "★ Any State", state: ANY_NODE_ID, isActive: false, transitionCount: 0, isGhost: false },
      });
    }

    return stateNodes;
  }, [allStateItems, transitionCountMap, STATE_POSITIONS_DYNAMIC, hasWildcards]);

  const initialEdges: Edge[] = useMemo(
    () =>
      transitions.flatMap((t, ti) => {
        const isWildcard = t.from_states.length === 0;
        const sources: string[] = isWildcard ? [ANY_NODE_ID] : t.from_states;
        return sources.flatMap((fromState: string, si: number) => {
          const target = t.to_state === "__same__"
            ? (isWildcard ? null : fromState)
            : t.to_state;
          if (!target) return []; // skip __same__ from ANY
          if (!target.trim()) return [];
          const isSelf = target === fromState;
          const edgeColor = isWildcard ? "#D1A23B" : "#636366";
          return [{
            id: `e-${ti}-${si}`,
            type: "straight",
            source: fromState,
            target,
            label: `${t.intent || "*"} → ${actionLabel(t.action, customSkills)}`,
            labelStyle: { fontSize: 10, fill: "#636366" },
            labelBgStyle: { fill: "white", fillOpacity: 0.9 },
            labelBgPadding: [4, 4] as [number, number],
            labelBgBorderRadius: 4,
            markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
            style: {
              stroke: edgeColor,
              strokeWidth: isWildcard ? 1.5 : 2,
              strokeDasharray: isWildcard ? "6 3" : (isSelf ? "4 3" : undefined),
              opacity: isWildcard ? 0.6 : 1,
            },
            data: { transition: t, fromState, isWildcard },
          }];
        });
      }),
    [transitions, customSkills] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Track whether we've done the first load so we don't re-init on every render
  const loadedTransitionsRef = useRef<string>("");
  const loadedNodesRef = useRef<string>("");

  // Restore saved viewport once on first mount
  const viewportRestoredRef = useRef(false);
  useEffect(() => {
    if (viewportRestoredRef.current) return;
    viewportRestoredRef.current = true;
    if (savedLayout?.viewport) {
      setViewport(savedLayout.viewport);
    }
  }, [savedLayout, setViewport]);

  // Sync transitions → edges only when the server data actually changes
  useEffect(() => {
    const key = JSON.stringify(transitions);
    if (key === loadedTransitionsRef.current) return;
    loadedTransitionsRef.current = key;
    setEdges(initialEdges);
    setIsDirty(false);
  }, [transitions]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync nodes whenever the state list or transition counts change
  useEffect(() => {
    const key = JSON.stringify(allStateItems) + JSON.stringify(transitionCountMap) + String(hasWildcards);
    if (key === loadedNodesRef.current) return;
    loadedNodesRef.current = key;
    setNodes(initialNodes);
  }, [allStateItems, transitionCountMap, hasWildcards]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync active node highlight into node data
  useEffect(() => {
    setNodes((ns) =>
      ns.map((n) => ({
        ...n,
        data: { ...n.data, isActive: activeState === n.id },
      }))
    );
  }, [activeState, setNodes]);

  // Persist node positions whenever they change (debounced 500ms)
  const layoutSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onNodesChangeWithPersist = useCallback(
    (changes: Parameters<typeof onNodesChange>[0]) => {
      onNodesChange(changes);
      // Debounce layout save
      if (layoutSaveTimerRef.current) clearTimeout(layoutSaveTimerRef.current);
      layoutSaveTimerRef.current = setTimeout(() => {
        setNodes((currentNodes) => {
          const positions: Record<string, { x: number; y: number }> = {};
          currentNodes.forEach((n) => { positions[n.id] = n.position; });
          // We don't have viewport here easily, save what we have; viewport is saved onMoveEnd
          const existing = loadLayout(tenantId);
          saveLayout(tenantId, positions, existing?.viewport ?? { x: 0, y: 0, zoom: 1 });
          return currentNodes;
        });
      }, 500);
    },
    [onNodesChange, setNodes, tenantId]
  );

  // ── Edge click → edit transition ───────────────────────────

  const onEdgeClick = useCallback(
    (_: MouseEvent, edge: Edge) => {
      setSelectedEdge(edge);
      const t: FlowTransition = edge.data?.transition ?? {};
      // Map FlowTransition → EditingTransition
      // from_states: [] = wildcard → fromState: "" (displayed as FROM_ANY sentinel)
      setEditingTransition({
        fromState: edge.data?.fromState ?? (t.from_states?.length > 0 ? t.from_states[0] : ""),
        to_state: t.to_state ?? "",
        intent: t.intent ?? "",
        action: t.action ?? "faq",
        static_message: t.static_message,
        enabled: t.enabled ?? true,
      });
    },
    []
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const isFromAny = connection.source === ANY_NODE_ID;
      const newEdge: Edge = {
        ...connection,
        id: `e-new-${Date.now()}`,
        source: connection.source ?? "idle",
        target: connection.target ?? "idle",
        label: "new",
        markerEnd: { type: MarkerType.ArrowClosed },
        data: {
          transition: {
            from_states: isFromAny ? [] : [connection.source ?? "idle"],
            to_state: connection.target ?? "idle",
            intent: "",
            action: "faq",
            enabled: true,
          } satisfies FlowTransition,
          fromState: connection.source,
          isWildcard: isFromAny,
        },
      };
      setEdges((es) => addEdge(newEdge, es));
      setSelectedEdge(newEdge);
      // Map to EditingTransition for the editor panel
      setEditingTransition({
        fromState: connection.source ?? "",
        to_state: connection.target ?? "",
        intent: "",
        action: "faq",
        enabled: true,
      });
      setIsDirty(true);
    },
    [setEdges]
  );

  const saveEdgeTransition = useCallback(() => {
    if (!editingTransition) return;

    // Convert EditingTransition → FlowTransition
    // fromState: "" means wildcard → from_states: []
    const fromState = editingTransition.fromState ?? "";
    const flowT: FlowTransition = {
      intent: editingTransition.intent ?? "",
      from_states: fromState ? [fromState] : [],
      to_state: editingTransition.to_state ?? "__same__",
      action: editingTransition.action ?? "faq",
      static_message: editingTransition.static_message,
      enabled: editingTransition.enabled ?? true,
    };

    if (!selectedEdge) {
      // ── New transition (created via button, not canvas drag) ──
      const isWildcard = flowT.from_states.length === 0;
      const sources = isWildcard ? [ANY_NODE_ID] : flowT.from_states;
      const newEdges: Edge[] = sources.flatMap((src, si) => {
        const target = flowT.to_state === "__same__" ? (isWildcard ? flowT.to_state : src) : flowT.to_state;
        if (target === "__same__" && isWildcard) return [];
        if (!target || !src) return [];
        const edgeColor = isWildcard ? "#D1A23B" : "#636366";
        return [{
          id: `e-new-${Date.now()}-${si}`,
          type: "straight",
          source: src,
          target,
          label: `${flowT.intent || "*"} → ${actionLabel(flowT.action, customSkills)}`,
          labelStyle: { fontSize: 10, fill: "#636366" },
          labelBgStyle: { fill: "white", fillOpacity: 0.9 },
          labelBgPadding: [4, 4] as [number, number],
          labelBgBorderRadius: 4,
          markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
          style: { stroke: edgeColor, strokeWidth: isWildcard ? 1.5 : 2, strokeDasharray: isWildcard ? "6 3" : undefined, opacity: isWildcard ? 0.55 : 1 },
          data: { transition: flowT, fromState: src, isWildcard },
        }];
      });
      // If adding a wildcard transition and no ANY node exists yet, add it
      if (isWildcard) {
        setNodes((ns) => {
          if (ns.find((n) => n.id === ANY_NODE_ID)) return ns;
          return [{
            id: ANY_NODE_ID,
            type: "anyNode" as any,
            position: ANY_NODE_POSITION,
            data: { label: "★ Any State", state: ANY_NODE_ID, isActive: false, transitionCount: 0 },
          }, ...ns];
        });
      }
      setEdges((es) => [...es, ...newEdges]);
      setIsDirty(true);
      pendingSaveRef.current = true;
      setEditingTransition(null);
      return;
    }

    // ── Editing existing edge ──
    setEdges((es) =>
      es.map((e) => {
        if (e.id !== selectedEdge.id) return e;
        const isWild = e.data?.isWildcard;
        const edgeColor = isWild ? "#D1A23B" : "#636366";
        return {
          ...e,
          label: `${flowT.intent || "*"} → ${actionLabel(flowT.action, customSkills)}`,
          style: { stroke: edgeColor, strokeWidth: isWild ? 1.5 : 2, strokeDasharray: isWild ? "6 3" : undefined, opacity: isWild ? 0.55 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
          data: { transition: flowT, fromState: e.data?.fromState, isWildcard: isWild },
        };
      })
    );
    setIsDirty(true);
    pendingSaveRef.current = true;
    setSelectedEdge(null);
    setEditingTransition(null);
  }, [selectedEdge, editingTransition, setEdges]);

  const deleteEdge = useCallback(() => {
    if (!selectedEdge) return;
    setEdges((es) => es.filter((e) => e.id !== selectedEdge.id));
    setIsDirty(true);
    pendingSaveRef.current = true;
    setSelectedEdge(null);
    setEditingTransition(null);
  }, [selectedEdge, setEdges]);

  // ── Save all transitions ────────────────────────────────────

  const saveAll = useCallback(async () => {
    // Sanitize: strip "__any__" sentinel from from_states before sending to backend
    const newTransitions: FlowTransition[] = edges
      .map((e) => e.data?.transition)
      .filter(Boolean)
      .map((t: FlowTransition) => ({
        ...t,
        from_states: t.from_states.filter((s: string) => s !== "__any__"),
      }));
    try {
      await replaceTransitions.mutateAsync(newTransitions);
      setIsDirty(false);
      toast.success("FSM transitions saved");
    } catch {
      toast.error("Failed to save transitions");
    }
  }, [edges, replaceTransitions]);

  // Auto-save when edges are modified (add / edit / delete) via the overlay editor
  useEffect(() => {
    if (!pendingSaveRef.current) return;
    pendingSaveRef.current = false;
    saveAll();
  }, [edges]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Full-canvas ReactFlow ──────────────────────── */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChangeWithPersist}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onEdgeClick={onEdgeClick}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView={!savedLayout}
        fitViewOptions={{ padding: 0.18 }}
        defaultEdgeOptions={{ type: "straight", animated: false }}
        onPaneClick={() => { setSelectedEdge(null); setEditingTransition(null); }}
        onMoveEnd={(_, viewport) => {
          // Persist viewport (zoom + pan) after the user stops moving
          setNodes((currentNodes) => {
            const positions: Record<string, { x: number; y: number }> = {};
            currentNodes.forEach((n) => { positions[n.id] = n.position; });
            saveLayout(tenantId, positions, viewport);
            return currentNodes;
          });
        }}
      >
        <Background gap={16} size={1} color="#e8e8ed" />
        <Controls position="bottom-left" />
        <MiniMap nodeColor={(n) => n.data?.isGhost ? "#e2e8f0" : "#c7d2fe"} position="bottom-right" />
      </ReactFlow>

      {/* ── Top toolbar ──────────────────────────────── */}
      <div className="absolute top-4 left-4 flex items-center gap-2 z-10">
        <Button
          size="sm"
          variant={isDirty ? "default" : "outline"}
          className="shadow-sm"
          onClick={saveAll}
          disabled={!isDirty}
        >
          <Save className="h-3.5 w-3.5 mr-1.5" />
          {isDirty ? "Save Changes" : "Saved"}
        </Button>

        <div className="h-4 w-px bg-slate-200" />

        <Button
          size="sm"
          variant="outline"
          className="shadow-sm bg-white"
          onClick={() => { setSelectedEdge(null); setEditingTransition({ intent: "", action: "faq", fromState: "", to_state: "", enabled: true }); }}
        >
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New Transition
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="shadow-sm bg-white"
          onClick={() => setShowIntentDialog(true)}
        >
          <Brain className="h-3.5 w-3.5 mr-1.5" />
          Intents
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="shadow-sm bg-white"
          onClick={() => setShowStatesDialog(true)}
        >
          <Layers className="h-3.5 w-3.5 mr-1.5" />
          States
        </Button>
      </div>

      {/* ── Help button (top-right) ───────────────────── */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        {!editingTransition && (
          <Button
            size="sm"
            variant="outline"
            className="shadow-sm bg-white/95 backdrop-blur-sm gap-1.5"
            onClick={() => setShowHelp((v) => !v)}
          >
            <HelpCircle className="h-3.5 w-3.5" />
            Help
          </Button>
        )}
      </div>

      {/* ── Help popover ─────────────────────────────── */}
      {showHelp && !editingTransition && (
        <div className="absolute top-14 right-4 z-30 w-80 bg-white rounded-2xl border shadow-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b bg-slate-50">
            <div className="font-semibold text-sm text-slate-800">FSM Editor — How it works</div>
            <button
              onClick={() => setShowHelp(false)}
              className="rounded-md p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="p-4 space-y-4 text-sm text-slate-700">
            <HelpSection icon="🔵" title="Nodes = States">
              Each box represents a conversation state (e.g. <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">faq_answer</code>, <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">checkout</code>). Drag nodes freely — positions are saved automatically.
            </HelpSection>
            <HelpSection icon="➡️" title="Arrows = Transitions">
              An arrow means: <em>"when intent X is detected in state A, execute action Y and move to state B"</em>. Click any arrow to edit it.
            </HelpSection>
            <HelpSection icon="🟡" title="★ ANY STATE node">
              Transitions originating from <strong>★ ANY</strong> apply regardless of the current state — useful for global intents like <em>goodbye</em> or <em>complaint</em>.
            </HelpSection>
            <HelpSection icon="🟣" title="Connection handles">
              Hover a node to reveal <span className="text-violet-500 font-medium">purple dots</span> (source) and <span className="text-emerald-500 font-medium">green dots</span> (target) on each side. Drag from any dot to create a connection — just like draw.io.
            </HelpSection>
            <HelpSection icon="💾" title="Layout persistence">
              Node positions, zoom, and pan are saved in your browser automatically. Use <strong>Save Changes</strong> (top-left) to commit transition rules to the server.
            </HelpSection>
            <HelpSection icon="🎯" title="Intent wildcard">
              Leave Intent blank (wildcard) on a transition to match <em>any</em> detected intent from that state.
            </HelpSection>
          </div>
        </div>
      )}

      {/* ── Transition editor overlay ─────────────────── */}
      {editingTransition && (
        <div className="absolute top-4 right-4 z-20">
          <TransitionEditor
            transition={editingTransition}
            intents={intents}
            actions={actions}
            customSkills={customSkills}
            allStates={fsmStateItems}
            onChange={setEditingTransition}
            onSave={saveEdgeTransition}
            onDelete={deleteEdge}
            onCancel={() => { setSelectedEdge(null); setEditingTransition(null); }}
          />
        </div>
      )}

      {/* ── Intent manager dialog ─────────────────────── */}
      <IntentManagerDialog
        tenantId={tenantId}
        open={showIntentDialog}
        onClose={() => setShowIntentDialog(false)}
        intents={intents}
      />

      {/* ── States manager dialog ─────────────────────── */}
      <StatesManagerDialog
        tenantId={tenantId}
        open={showStatesDialog}
        onClose={() => setShowStatesDialog(false)}
        states={fsmStateItems as { key: string; label: string; is_default?: boolean }[]}
      />
    </div>
  );
}

// ─── Help section sub-component ───────────────────────────────

function HelpSection({ icon, title, children }: { icon: string; title: string; children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="text-base shrink-0 mt-0.5">{icon}</span>
      <div>
        <div className="font-semibold text-slate-800 mb-0.5">{title}</div>
        <div className="text-slate-500 text-xs leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

// ─── Transition editor ─────────────────────────────────────────

// When editing, we work with a single from/to state pair + the transition data.
// The FlowTransition.from_states[] is managed at save time.
interface EditingTransition {
  /** "" means wildcard (any state) — maps to from_states: [] */
  fromState: string;
  to_state: string;
  intent: string;
  action: string;
  static_message?: string;
  enabled: boolean;
}

function TransitionEditor({
  transition,
  intents,
  actions,
  customSkills,
  allStates,
  onChange,
  onSave,
  onDelete,
  onCancel,
}: {
  transition: Partial<EditingTransition>;
  intents: IntentDefinition[];
  actions: ActionCatalogItem[];
  customSkills: SkillConfig[];
  allStates: { key: string; label: string }[];
  onChange: (t: Partial<EditingTransition>) => void;
  onSave: () => void;
  onDelete: () => void;
  onCancel: () => void;
}) {

  return (
    <div className="w-[300px] bg-white rounded-2xl border border-slate-200 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-violet-500" />
          <span className="font-semibold text-sm text-slate-800">Edit Transition</span>
        </div>
        <button
          onClick={onCancel}
          className="rounded-md p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* From State */}
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-slate-700">
            From State
            <span className="ml-1.5 text-slate-400 font-normal">(Any = applies from every state)</span>
          </Label>
          <Select
            value={transition.fromState || FROM_ANY}
            onValueChange={(v) => onChange({ ...transition, fromState: v === FROM_ANY ? "" : v })}
          >
            <SelectTrigger className="h-9 text-sm border-slate-200 focus:ring-violet-500 focus:border-violet-400">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={FROM_ANY} className="text-sm">
                <span className="text-amber-600 font-medium">✦ Any State</span>
                <span className="ml-1.5 text-slate-400 text-xs">(wildcard)</span>
              </SelectItem>
              {allStates.map((s) => (
                <SelectItem key={s.key} value={s.key} className="text-sm">
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Arrow visual */}
        <div className="flex items-center gap-2 text-slate-300 text-xs">
          <div className="flex-1 h-px bg-slate-100" />
          <span className="shrink-0">↓ transitions to</span>
          <div className="flex-1 h-px bg-slate-100" />
        </div>

        {/* To State */}
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-slate-700">To State</Label>
          <Select
            value={transition.to_state || ""}
            onValueChange={(v) => onChange({ ...transition, to_state: v })}
          >
            <SelectTrigger className="h-9 text-sm border-slate-200 focus:ring-violet-500 focus:border-violet-400">
              <SelectValue placeholder="Select target state…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__same__" className="text-sm">
                <span className="text-slate-500">↩ Same State</span>
                <span className="ml-1.5 text-slate-400 text-xs">(no change)</span>
              </SelectItem>
              {allStates.map((s) => (
                <SelectItem key={s.key} value={s.key} className="text-sm">
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="h-px bg-slate-100" />

        {/* Intent */}
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-slate-700">
            Intent
            <span className="ml-1.5 text-slate-400 font-normal">(blank = any intent)</span>
          </Label>
          <Select
            value={transition.intent || INTENT_WILDCARD}
            onValueChange={(v) => onChange({ ...transition, intent: v === INTENT_WILDCARD ? "" : v })}
          >
            <SelectTrigger className="h-9 text-sm border-slate-200 focus:ring-violet-500 focus:border-violet-400">
              <SelectValue placeholder="Any intent" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={INTENT_WILDCARD} className="text-sm text-slate-500">
                — Any intent (wildcard)
              </SelectItem>
              {intents.map((i) => (
                <SelectItem key={i.key} value={i.key} className="text-sm">
                  {i.name ?? i.key}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Action */}
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-slate-700">Action</Label>
          <Select
            value={transition.action}
            onValueChange={(v) => onChange({ ...transition, action: v })}
          >
            <SelectTrigger className="h-9 text-sm border-slate-200 focus:ring-violet-500 focus:border-violet-400">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {/* Built-in catalog actions */}
              {(actions.length > 0 ? actions.map((a) => a.key) : Object.keys(ACTION_LABELS)).map((a) => (
                <SelectItem key={a} value={a} className="text-sm">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: ACTION_COLORS[a] ?? "#94a3b8" }} />
                    {ACTION_LABELS[a] ?? a}
                  </div>
                </SelectItem>
              ))}
              {/* Custom conversational personas */}
              {customSkills.length > 0 && (
                <>
                  <div className="px-3 pt-3 pb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-widest border-t mt-1">
                    Custom Personas
                  </div>
                  {customSkills.map((skill) => (
                    <SelectItem key={skill.action} value={skill.action} className="text-sm">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full shrink-0 bg-rose-500" />
                        {skill.name ?? skill.action.replace("conversational__", "").replace(/_/g, " ")}
                      </div>
                    </SelectItem>
                  ))}
                </>
              )}
            </SelectContent>
          </Select>
        </div>

        {/* Static message (only for static_reply) */}
        {transition.action === "static_reply" && (
          <div className="space-y-1.5">
            <Label className="text-xs font-medium text-slate-700">Static Message</Label>
            <Input
              className="text-sm h-9 border-slate-200 focus-visible:ring-violet-500"
              placeholder="Message to send…"
              value={transition.static_message ?? ""}
              onChange={(e) => onChange({ ...transition, static_message: e.target.value })}
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 pb-4 flex items-center gap-2">
        <Button
          size="sm"
          className="flex-1 h-9 bg-violet-600 hover:bg-violet-700 text-white font-medium"
          onClick={onSave}
        >
          <Save className="h-3.5 w-3.5 mr-1.5" />
          Apply
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-9 w-9 p-0 border-red-200 text-red-500 hover:bg-red-50 hover:border-red-300 hover:text-red-600"
          onClick={onDelete}
          title="Delete transition"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
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

// ─── States manager dialog ─────────────────────────────────────

function StatesManagerDialog({
  tenantId,
  open,
  onClose,
  states,
}: {
  tenantId: string;
  open: boolean;
  onClose: () => void;
  states: { key: string; label: string; is_default?: boolean }[];
}) {
  const createState = useCreateFSMState(tenantId);
  const deleteState = useDeleteFSMState(tenantId);
  const [newKey, setNewKey] = useState("");
  const [newLabel, setNewLabel] = useState("");

  const slug = newKey
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);

  const conflict = slug ? states.some((s) => s.key === slug) : false;

  async function handleCreate() {
    if (!slug || conflict) return;
    await createState.mutateAsync({ key: slug, label: newLabel.trim() || slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) });
    setNewKey("");
    setNewLabel("");
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4" />
            Manage FSM States
          </DialogTitle>
          <DialogDescription>
            Add or remove states in your conversation flow. Only <strong>idle</strong> is required and cannot be removed.
          </DialogDescription>
        </DialogHeader>

        {/* Add new state */}
        <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
          <div className="text-xs font-medium">Add Custom State</div>
          <div className="flex gap-2">
            <Input
              placeholder="State key (e.g. upselling)"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className="text-xs h-8 font-mono flex-1"
            />
            <Input
              placeholder="Display label (optional)"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              className="text-xs h-8 flex-1"
            />
            <Button
              size="sm"
              className="h-8 shrink-0"
              disabled={!slug || conflict || createState.isPending}
              loading={createState.isPending}
              onClick={handleCreate}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add
            </Button>
          </div>
          {slug && (
            <div className="text-[11px] font-mono text-muted-foreground">
              Key: <span className={conflict ? "text-destructive" : "text-foreground"}>{slug}</span>
              {conflict && <span className="text-destructive ml-1">(already exists)</span>}
            </div>
          )}
        </div>

        {/* States list */}
        <div className="flex-1 overflow-y-auto space-y-1 min-h-0">
          {states.map((s) => {
            const isImmutable = s.key === "idle";
            return (
              <div
                key={s.key}
                className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="h-2 w-2 rounded-full bg-slate-400 shrink-0" />
                  <span className="font-medium truncate">{s.label}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">{s.key}</span>
                  {isImmutable && (
                    <Badge variant="secondary" className="text-[9px] h-4 px-1.5">required</Badge>
                  )}
                </div>
                {!isImmutable && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive shrink-0"
                    loading={deleteState.isPending}
                    onClick={() => deleteState.mutate(s.key)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}