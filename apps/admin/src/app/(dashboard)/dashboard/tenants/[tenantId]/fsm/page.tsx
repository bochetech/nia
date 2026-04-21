"use client";

import {
  use,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
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
  getBezierPath,
  BaseEdge,
  EdgeLabelRenderer,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
  type EdgeTypes,
  type Viewport,
  type EdgeProps,
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
import type {
  FlowTransition,
  IntentDefinition,
  ActionCatalogItem,
  SkillConfig,
} from "@/lib/api";
import { ACTION_COLORS, ACTION_LABELS, cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Save,
  Plus,
  Trash2,
  Edit,
  Brain,
  Layers,
  X,
  ChevronDown,
  ArrowRight,
  Circle,
  Workflow,
  Undo2,
} from "lucide-react";
import { toast } from "sonner";
import { useSession } from "next-auth/react";
import { useTheme } from "next-themes";

const ANY_NODE_ID = "__any__";
const INTENT_WILDCARD = "__wildcard__";
const FROM_ANY = "__any__";

interface SavedLayout {
  positions: Record<string, { x: number; y: number }>;
  viewport?: Viewport;
}

function layoutKey(tid: string) {
  return `nia_flow_layout_v2_${tid}`;
}

function loadLayout(tid: string): SavedLayout | null {
  try {
    const raw = localStorage.getItem(layoutKey(tid));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function persistLayout(
  tid: string,
  positions: Record<string, { x: number; y: number }>,
  viewport?: Viewport,
) {
  try {
    localStorage.setItem(layoutKey(tid), JSON.stringify({ positions, viewport }));
  } catch {
    /* quota */
  }
}

function autoPos(idx: number, total: number): { x: number; y: number } {
  if (total <= 1) return { x: 400, y: 300 };
  const r = Math.max(200, total * 45);
  const a = (idx / total) * 2 * Math.PI - Math.PI / 2;
  return { x: 400 + Math.cos(a) * r, y: 300 + Math.sin(a) * r };
}

function actLabel(
  action: string,
  custom?: { action: string; name?: string }[],
): string {
  if (action.startsWith("conversational__")) {
    const s = custom?.find((c) => c.action === action);
    if (s?.name) return s.name;
    return action.replace("conversational__", "").replace(/_/g, " ");
  }
  return ACTION_LABELS[action] ?? action;
}

function actColor(action: string): string {
  if (action.startsWith("conversational__"))
    return ACTION_COLORS.conversational ?? "#FF2D55";
  return ACTION_COLORS[action] ?? "#8E8E93";
}

const DOT: React.CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: "50%",
  border: "none",
  opacity: 0,
  transition: "opacity .15s",
};

function StateNode({ data, selected }: { data: any; selected: boolean }) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const { isGhost, isAny } = data;
  const accentColor = isAny ? "#f59e0b" : isGhost ? "#4b5563" : "#6366f1";
  const dotBg = accentColor;
  const tgtBg = "#10b981";

  const nodeBg = isGhost
    ? (isDark ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.02)")
    : (isDark ? "#111118" : "#ffffff");
  const nodeBorder = selected ? accentColor : (isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)");
  const textMain = isGhost ? (isDark ? "#555" : "#94a3b8") : isAny ? "#f59e0b" : (isDark ? "#e2e2f0" : "#0f172a");
  const textMuted = isDark ? "#444" : "#94a3b8";
  const textKey = isDark ? "#555" : "#64748b";
  const ghostBar = isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";

  return (
    <div
      className="group/node relative [&_.react-flow__handle]:hover:opacity-100"
      style={{
        minWidth: 164,
        borderRadius: 10,
        overflow: "hidden",
        border: `1px solid ${nodeBorder}`,
        background: nodeBg,
        boxShadow: selected
          ? `0 0 0 2px ${accentColor}33, 0 4px 16px rgba(0,0,0,.4)`
          : isDark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 2px 8px rgba(0,0,0,0.08)",
        transition: "border .15s, box-shadow .15s",
        cursor: "pointer",
      }}
    >
      {/* Left accent bar */}
      <div
        style={{
          position: "absolute", left: 0, top: 0, bottom: 0, width: 3,
          background: isGhost
            ? ghostBar
            : `linear-gradient(180deg, ${accentColor}, ${accentColor}99)`,
        }}
      />

      <div style={{ padding: "10px 14px 10px 17px" }}>
        {isAny && (
          <div style={{ fontSize: 11, color: "#f59e0b", marginBottom: 2 }}>★ Wildcard</div>
        )}
        <div
          style={{
            fontSize: 13, fontWeight: 600, lineHeight: 1.3,
            color: textMain,
          }}
        >
          {data.label}
        </div>
        {isGhost ? (
          <div style={{ fontSize: 10, color: textMuted, marginTop: 2, fontStyle: "italic" }}>
            ghost — not created
          </div>
        ) : data.key && data.key !== data.label ? (
          <div
            style={{
              fontSize: 10, color: textKey, marginTop: 2,
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          >
            {data.key}
          </div>
        ) : data.transitionCount > 0 ? (
          <div style={{ fontSize: 10, color: textMuted, marginTop: 2 }}>
            {data.transitionCount} transition{data.transitionCount !== 1 ? "s" : ""}
          </div>
        ) : null}
      </div>

      {data.isActive && (
        <div
          style={{
            position: "absolute", top: 8, right: 8,
            width: 7, height: 7, borderRadius: "50%",
            background: "#10b981",
            boxShadow: "0 0 6px #10b981",
          }}
          className="animate-pulse"
        />
      )}

      {/* Handles */}
      <Handle type="source" position={Position.Top}    id="top"    style={{ ...DOT, background: dotBg, top: -4 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ ...DOT, background: dotBg, bottom: -4 }} />
      <Handle type="source" position={Position.Left}   id="left"   style={{ ...DOT, background: dotBg, left: -4 }} />
      <Handle type="source" position={Position.Right}  id="right"  style={{ ...DOT, background: dotBg, right: -4 }} />
      <Handle type="target" position={Position.Top}    id="t-top"    style={{ ...DOT, background: tgtBg, top: -4 }} />
      <Handle type="target" position={Position.Bottom} id="t-bottom" style={{ ...DOT, background: tgtBg, bottom: -4 }} />
      <Handle type="target" position={Position.Left}   id="t-left"   style={{ ...DOT, background: tgtBg, left: -4 }} />
      <Handle type="target" position={Position.Right}  id="t-right"  style={{ ...DOT, background: tgtBg, right: -4 }} />
    </div>
  );
}

function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  markerEnd,
}: EdgeProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const color = data?.color ?? "#8E8E93";
  const isWild = data?.isWildcard;
  const offset: number = data?.offset ?? 0;

  // ── Self-loop detection ──────────────────────────────
  const isSelfLoop = Math.abs(sourceX - targetX) < 2 && Math.abs(sourceY - targetY) < 2;

  // Build path + label position
  let path: string;
  let lx: number;
  let ly: number;

  if (isSelfLoop) {
    // Draw a circular arc above the node
    const r = 40;
    const sx = sourceX;
    const sy = sourceY - 4; // top handle
    path = `M ${sx} ${sy} C ${sx - r * 2} ${sy - r * 3}, ${sx + r * 2} ${sy - r * 3}, ${sx} ${sy}`;
    lx = sx;
    ly = sy - r * 2.8;
  } else {
    const dx = targetX - sourceX;
    const dy = targetY - sourceY;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const ox = (-dy / len) * offset;
    const oy = (dx / len) * offset;

    [path, lx, ly] = getBezierPath({
      sourceX: sourceX + ox,
      sourceY: sourceY + oy,
      targetX: targetX + ox,
      targetY: targetY + oy,
      sourcePosition,
      targetPosition,
      curvature: 0.25,
    });
  }

  return (
    <>
      <path d={path} fill="none" stroke="transparent" strokeWidth={20} className="react-flow__edge-interaction" />
      <BaseEdge
        id={id}
        path={path}
        markerEnd={isSelfLoop ? undefined : markerEnd}
        style={{
          stroke: color,
          strokeWidth: selected ? 2.5 : isWild ? 1.5 : 2,
          strokeDasharray: isWild ? "6 4" : undefined,
          opacity: isWild ? 0.7 : 1,
          transition: "stroke .2s, stroke-width .2s",
        }}
      />
      {/* Manual arrowhead for self-loops */}
      {isSelfLoop && (
        <path
          d={`M ${sourceX - 6} ${sourceY - 8} L ${sourceX} ${sourceY - 2} L ${sourceX + 6} ${sourceY - 8}`}
          fill="none"
          stroke={color}
          strokeWidth={selected ? 2.5 : 2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
      <EdgeLabelRenderer>
        <div
          className="absolute pointer-events-auto cursor-pointer transition-all duration-200"
          style={{
            transform: `translate(-50%, -50%) translate(${lx}px,${ly}px)`,
            borderRadius: 6,
            padding: "4px 10px",
            fontSize: 10,
            fontWeight: 500,
            lineHeight: 1.4,
            background: isDark ? "#111118" : "#ffffff",
            borderTop: `1px solid ${isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
            borderRight: `1px solid ${isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
            borderBottom: `1px solid ${isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
            borderLeft: `3px solid ${color}`,
            boxShadow: selected ? `0 0 0 1px ${color}44, 0 4px 12px rgba(0,0,0,.5)` : isDark ? "0 2px 8px rgba(0,0,0,.4)" : "0 2px 8px rgba(0,0,0,.08)",
            whiteSpace: "nowrap",
          }}
        >
          <div style={{ color: isDark ? "#555" : "#94a3b8" }}>{data?.intentLabel || "Any intent"}</div>
          <div style={{ color, fontWeight: 600 }}>{data?.actionLabel || "Action"}</div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const nodeTypes: NodeTypes = { stateNode: StateNode };
const edgeTypes: EdgeTypes = { flow: FlowEdge };

interface EditTrans {
  fromState: string;
  to_state: string;
  intent: string;
  action: string;
  static_message?: string;
  bot_prompt?: string;
  suggested_replies?: string[];
  enabled: boolean;
}

export default function FSMPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  return (
    <ReactFlowProvider>
      <FlowCanvas tenantId={tenantId} />
    </ReactFlowProvider>
  );
}

function FlowCanvas({ tenantId }: { tenantId: string }) {
  const { data: session } = useSession();
  const { setViewport } = useReactFlow();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // Theme-aware canvas tokens
  const canvasBg = isDark ? "#09090f" : "#f1f5f9";
  const cardBg = isDark ? "#111118" : "#ffffff";
  const panelBg = isDark ? "#0e0e17" : "#ffffff";
  const borderColor = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  const gridColor = isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.08)";
  const textPrimary = isDark ? "#e2e2f0" : "#0f172a";
  const textMuted = isDark ? "#888" : "#64748b";
  const iconColor = isDark ? "#818cf8" : "#6366f1";

  const { data: intentsData } = useIntents(tenantId);
  const { data: actionsData } = useActions(tenantId);
  const { data: transitionsData } = useTransitions(tenantId);
  const { data: skillsData } = useSkills(tenantId);
  const { data: statesData } = useFSMStates(tenantId);
  const replaceTransitions = useReplaceTransitions(tenantId);

  const intents: IntentDefinition[] = intentsData?.data ?? [];
  const actions: ActionCatalogItem[] = actionsData?.data ?? [];
  const transitions: FlowTransition[] = transitionsData?.data ?? [];
  const customSkills: SkillConfig[] = useMemo(
    () => (skillsData?.data ?? []).filter((s: SkillConfig) => s.action.startsWith("conversational__")),
    [skillsData],
  );

  const fsmStates: { key: string; label: string; is_default?: boolean }[] = useMemo(() => {
    if (statesData?.data?.length) return statesData.data;
    return [{ key: "idle", label: "Idle" }];
  }, [statesData]);

  const allStates = useMemo(() => {
    const known = new Set(fsmStates.map((s) => s.key));
    const ghosts = new Set<string>();
    transitions.forEach((t) => {
      t.from_states.forEach((s) => { if (!known.has(s)) ghosts.add(s); });
      if (t.to_state && t.to_state !== "__same__" && !known.has(t.to_state)) ghosts.add(t.to_state);
    });
    return [
      ...fsmStates.map((s) => ({ ...s, isGhost: false })),
      ...[...ghosts].map((k) => ({
        key: k,
        label: k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        is_default: false,
        isGhost: true,
      })),
    ];
  }, [fsmStates, transitions]);

  const hasWild = useMemo(() => transitions.some((t) => t.from_states.length === 0), [transitions]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const saved = useMemo(() => loadLayout(tenantId), []);

  const [selEdgeId, setSelEdgeId] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditTrans | null>(null);
  const [panel, setPanel] = useState<"none" | "transition" | "intents" | "states">("none");
  const [isDirty, setIsDirty] = useState(false);

  const tCountMap = useMemo(() => {
    const m: Record<string, number> = {};
    transitions.forEach((t) => {
      t.from_states.forEach((s) => { m[s] = (m[s] ?? 0) + 1; });
      if (t.from_states.length === 0) m[ANY_NODE_ID] = (m[ANY_NODE_ID] ?? 0) + 1;
    });
    return m;
  }, [transitions]);

  const offsetMap = useMemo(() => {
    const pc: Record<string, number> = {};
    const pi: Record<string, number> = {};
    const off: Record<string, number> = {};
    const keys: { id: string; pk: string }[] = [];

    transitions.forEach((t, ti) => {
      const srcs = t.from_states.length === 0 ? [ANY_NODE_ID] : t.from_states;
      srcs.forEach((src, si) => {
        const tgt = t.to_state === "__same__" ? (t.from_states.length === 0 ? null : src) : t.to_state;
        if (!tgt) return;
        const a = src < tgt ? src : tgt;
        const b = src < tgt ? tgt : src;
        const pk = `${a}|${b}`;
        pc[pk] = (pc[pk] ?? 0) + 1;
        keys.push({ id: `e-${ti}-${si}`, pk });
      });
    });

    keys.forEach(({ id, pk }) => {
      const count = pc[pk];
      if (count <= 1) { off[id] = 0; return; }
      const idx = pi[pk] ?? 0;
      pi[pk] = idx + 1;
      off[id] = (idx - (count - 1) / 2) * 20;
    });
    return off;
  }, [transitions]);

  const initNodes: Node[] = useMemo(() => {
    const total = allStates.length + (hasWild ? 1 : 0);
    let idx = 0;
    const ns: Node[] = [];

    if (hasWild) {
      ns.push({
        id: ANY_NODE_ID,
        type: "stateNode",
        position: saved?.positions?.[ANY_NODE_ID] ?? { x: 60, y: 60 },
        data: { label: "\u2605 Any State", state: ANY_NODE_ID, isActive: false, transitionCount: tCountMap[ANY_NODE_ID] ?? 0, isGhost: false, isAny: true },
      });
      idx++;
    }

    allStates.forEach((s) => {
      ns.push({
        id: s.key,
        type: "stateNode",
        position: saved?.positions?.[s.key] ?? autoPos(idx, total),
        data: { label: s.label, state: s.key, isActive: false, transitionCount: tCountMap[s.key] ?? 0, isGhost: s.isGhost, isAny: false },
      });
      idx++;
    });
    return ns;
  }, [allStates, tCountMap, saved, hasWild]);

  const initEdges: Edge[] = useMemo(
    () =>
      transitions.flatMap((t, ti) => {
        const wild = t.from_states.length === 0;
        const srcs = wild ? [ANY_NODE_ID] : t.from_states;
        return srcs.flatMap((src, si) => {
          const tgt = t.to_state === "__same__" ? (wild ? null : src) : t.to_state;
          if (!tgt?.trim()) return [];
          const eid = `e-${ti}-${si}`;
          const c = actColor(t.action);
          const iDef = intents.find((i) => i.key === t.intent);
          return [{
            id: eid,
            type: "flow",
            source: src,
            target: tgt,
            markerEnd: { type: MarkerType.ArrowClosed, color: c, width: 16, height: 16 },
            data: {
              transition: t, fromState: src, isWildcard: wild, color: c,
              offset: offsetMap[eid] ?? 0,
              intentLabel: t.intent ? iDef?.name ?? t.intent : undefined,
              actionLabel: actLabel(t.action, customSkills),
            },
          }];
        });
      }),
    [transitions, intents, customSkills, offsetMap],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);

  // Wrap onEdgesChange so deletions also mark the canvas as dirty
  const onEdgesChangeTracked = useCallback(
    (changes: Parameters<typeof onEdgesChange>[0]) => {
      onEdgesChange(changes);
      if (changes.some((c) => c.type === "remove")) {
        setIsDirty(true);
      }
    },
    [onEdgesChange],
  );

  const loadedTRef = useRef("");
  const loadedNRef = useRef("");

  const vpRef = useRef(false);
  useEffect(() => {
    if (vpRef.current) return;
    vpRef.current = true;
    if (saved?.viewport) setViewport(saved.viewport);
  }, [saved, setViewport]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const k = JSON.stringify(transitions);
    if (k === loadedTRef.current) return;
    loadedTRef.current = k;
    setEdges(initEdges);
    setIsDirty(false);
  }, [transitions]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const k = JSON.stringify(allStates) + JSON.stringify(tCountMap) + String(hasWild);
    if (k === loadedNRef.current) return;
    loadedNRef.current = k;
    setNodes(initNodes);
  }, [allStates, tCountMap, hasWild]);

  const lTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onNC = useCallback(
    (changes: Parameters<typeof onNodesChange>[0]) => {
      onNodesChange(changes);
      if (lTimer.current) clearTimeout(lTimer.current);
      lTimer.current = setTimeout(() => {
        setNodes((ns) => {
          const pos: Record<string, { x: number; y: number }> = {};
          ns.forEach((n) => (pos[n.id] = n.position));
          const ex = loadLayout(tenantId);
          persistLayout(tenantId, pos, ex?.viewport);
          return ns;
        });
      }, 400);
    },
    [onNodesChange, setNodes, tenantId],
  );

  const onEdgeClick = useCallback((_: any, edge: Edge) => {
    setSelEdgeId(edge.id);
    const t: FlowTransition = edge.data?.transition ?? {};
    setEditing({
      fromState: edge.data?.fromState ?? (t.from_states?.length ? t.from_states[0] : ""),
      to_state: t.to_state ?? "",
      intent: t.intent ?? "",
      action: t.action ?? "faq",
      static_message: t.static_message,
      bot_prompt: t.bot_prompt,
      suggested_replies: t.suggested_replies ?? [],
      enabled: t.enabled ?? true,
    });
    setPanel("transition");
  }, []);

  const onConnect = useCallback((conn: Connection) => {
    const fromAny = conn.source === ANY_NODE_ID;
    const tr: FlowTransition = {
      intent: "", from_states: fromAny ? [] : [conn.source ?? "idle"],
      to_state: conn.target ?? "idle", action: "faq", enabled: true, suggested_replies: [],
    };
    const c = actColor("faq");
    const ne: Edge = {
      id: `e-new-${Date.now()}`, type: "flow",
      source: conn.source ?? "idle", target: conn.target ?? "idle",
      markerEnd: { type: MarkerType.ArrowClosed, color: c, width: 16, height: 16 },
      data: { transition: tr, fromState: conn.source, isWildcard: fromAny, color: c, offset: 0, actionLabel: actLabel("faq", customSkills) },
    };
    setEdges((es) => addEdge(ne, es));
    setSelEdgeId(ne.id);
    setEditing({
      fromState: conn.source ?? "", to_state: conn.target ?? "",
      intent: "", action: "faq", suggested_replies: [], enabled: true,
    });
    setPanel("transition");
    setIsDirty(true);
  }, [setEdges, customSkills]);

  const applyEdit = useCallback((upd: EditTrans) => {
    setEditing(upd);
    if (!selEdgeId) return;
    const c = actColor(upd.action);
    const iDef = intents.find((i) => i.key === upd.intent);
    setEdges((es) => es.map((e) => {
      if (e.id !== selEdgeId) return e;
      const ft: FlowTransition = {
        intent: upd.intent, from_states: upd.fromState ? [upd.fromState] : [],
        to_state: upd.to_state || "__same__", action: upd.action,
        static_message: upd.static_message, bot_prompt: upd.bot_prompt,
        suggested_replies: upd.suggested_replies?.filter(Boolean) ?? [], enabled: upd.enabled,
      };
      return {
        ...e,
        data: { ...e.data, transition: ft, color: c, intentLabel: upd.intent ? iDef?.name ?? upd.intent : undefined, actionLabel: actLabel(upd.action, customSkills) },
        markerEnd: { type: MarkerType.ArrowClosed, color: c, width: 16, height: 16 },
      };
    }));
    setIsDirty(true);
  }, [selEdgeId, setEdges, intents, customSkills]);

  const createNew = useCallback(() => {
    setSelEdgeId(null);
    setEditing({ fromState: "", to_state: "", intent: "", action: "faq", suggested_replies: [], enabled: true });
    setPanel("transition");
  }, []);

  const saveTrans = useCallback(() => {
    if (!editing) return;
    if (!selEdgeId) {
      if (!editing.to_state) { toast.error("Select a target state"); return; }
      const wild = !editing.fromState;
      const src = wild ? ANY_NODE_ID : editing.fromState;
      const c = actColor(editing.action);
      const iDef = intents.find((i) => i.key === editing.intent);
      const ft: FlowTransition = {
        intent: editing.intent, from_states: wild ? [] : [editing.fromState],
        to_state: editing.to_state, action: editing.action,
        static_message: editing.static_message, bot_prompt: editing.bot_prompt,
        suggested_replies: editing.suggested_replies?.filter(Boolean) ?? [], enabled: editing.enabled,
      };
      if (wild) {
        setNodes((ns) => {
          if (ns.find((n) => n.id === ANY_NODE_ID)) return ns;
          return [{ id: ANY_NODE_ID, type: "stateNode", position: { x: 60, y: 60 },
            data: { label: "\u2605 Any State", state: ANY_NODE_ID, isActive: false, transitionCount: 0, isGhost: false, isAny: true } }, ...ns];
        });
      }
      const ne: Edge = {
        id: `e-new-${Date.now()}`, type: "flow", source: src, target: editing.to_state,
        markerEnd: { type: MarkerType.ArrowClosed, color: c, width: 16, height: 16 },
        data: { transition: ft, fromState: src, isWildcard: wild, color: c, offset: 0,
          intentLabel: editing.intent ? iDef?.name ?? editing.intent : undefined, actionLabel: actLabel(editing.action, customSkills) },
      };
      setEdges((es) => [...es, ne]);
      setIsDirty(true);
      toast.success("Transition added");
    }
    setPanel("none");
    setSelEdgeId(null);
    setEditing(null);
  }, [editing, selEdgeId, intents, customSkills, setEdges, setNodes]);

  const deleteTrans = useCallback(() => {
    if (selEdgeId) {
      setEdges((es) => es.filter((e) => e.id !== selEdgeId));
      setIsDirty(true);
      toast.success("Transition removed");
    }
    setSelEdgeId(null);
    setEditing(null);
    setPanel("none");
  }, [selEdgeId, setEdges]);

  const saveAll = useCallback(async () => {
    setNodes((ns) => {
      const pos: Record<string, { x: number; y: number }> = {};
      ns.forEach((n) => (pos[n.id] = n.position));
      const ex = loadLayout(tenantId);
      persistLayout(tenantId, pos, ex?.viewport);
      return ns;
    });
    const newT: FlowTransition[] = edges
      .map((e) => e.data?.transition).filter(Boolean)
      .map((t: FlowTransition) => ({ ...t, from_states: t.from_states.filter((s: string) => s !== ANY_NODE_ID) }));
    try {
      await replaceTransitions.mutateAsync(newT);
      setIsDirty(false);
      toast.success("Conversation flow saved");
    } catch {
      toast.error("Failed to save flow");
    }
  }, [edges, replaceTransitions, tenantId, setNodes]);

  const closePanel = useCallback(() => { setPanel("none"); setSelEdgeId(null); setEditing(null); }, []);
  const panelOpen = panel !== "none";

  return (
    <div className="relative h-[calc(100vh-4rem)] flex overflow-hidden" style={{ background: canvasBg }}>
      <div className={cn("flex-1 transition-all duration-300 ease-out", panelOpen && "mr-[380px]")}>
        <ReactFlow
          nodes={nodes} edges={edges}
          onNodesChange={onNC} onEdgesChange={onEdgesChangeTracked}
          onConnect={onConnect} onEdgeClick={onEdgeClick}
          nodeTypes={nodeTypes} edgeTypes={edgeTypes}
          connectionMode={ConnectionMode.Loose}
          fitView={!saved} fitViewOptions={{ padding: 0.2 }}
          defaultEdgeOptions={{ type: "flow" }}
          onNodeClick={(_, n) => { if (!n.data?.isAny) setPanel("states"); }}
          onPaneClick={() => { if (panel !== "transition") setSelEdgeId(null); }}
          onMoveEnd={(_, vp) => {
            setNodes((ns) => {
              const pos: Record<string, { x: number; y: number }> = {};
              ns.forEach((n) => (pos[n.id] = n.position));
              persistLayout(tenantId, pos, vp);
              return ns;
            });
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} color={gridColor} />
          <Controls position="bottom-left" showInteractive={false}
            className="!rounded-xl overflow-hidden"
            style={{ background: cardBg, border: `1px solid ${borderColor}` } as React.CSSProperties} />
          <MiniMap
            nodeColor={(n) => n.data?.isAny ? "#f59e0b" : n.data?.isGhost ? (isDark ? "#2a2a3a" : "#e2e8f0") : "#6366f1"}
            maskColor={isDark ? "rgba(0,0,0,.4)" : "rgba(255,255,255,.6)"}
            style={{ background: cardBg, border: `1px solid ${borderColor}`, borderRadius: 10 } as React.CSSProperties}
            position="bottom-right" />
        </ReactFlow>

        {/* Top-left toolbar */}
        <div className="absolute top-4 left-4 flex items-center gap-2.5 z-10">
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-xl"
            style={{ background: cardBg, border: `1px solid ${borderColor}` }}
          >
            <Workflow className="h-4 w-4" style={{ color: iconColor }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: textPrimary }}>Conversation Flow</span>
          </div>
          <button
            onClick={saveAll}
            disabled={!isDirty || replaceTransitions.isPending}
            className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 transition-all"
            style={{
              fontSize: 13, fontWeight: 500,
              background: isDirty ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : cardBg,
              border: isDirty ? "none" : `1px solid ${borderColor}`,
              color: isDirty ? "#fff" : textMuted,
              cursor: isDirty ? "pointer" : "not-allowed",
              opacity: replaceTransitions.isPending ? 0.7 : 1,
            }}
          >
            <Save className="h-3.5 w-3.5" />
            {replaceTransitions.isPending ? "Saving…" : isDirty ? "Save Changes" : "Saved"}
          </button>
          {isDirty && (
            <span
              style={{
                fontSize: 10, borderRadius: 4, padding: "2px 8px",
                background: "rgba(245,158,11,0.12)", color: "#f59e0b",
                border: "1px solid rgba(245,158,11,0.2)",
              }}
            >
              Unsaved changes
            </span>
          )}
        </div>

        {/* Top-right toolbar */}
        <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
          {[
            { label: "Transition", icon: Plus, key: "transition" as const, onClick: createNew },
            { label: "Intents",    icon: Brain, key: "intents" as const,    onClick: () => setPanel((p) => p === "intents" ? "none" : "intents") },
            { label: "States",     icon: Layers, key: "states" as const,   onClick: () => setPanel((p) => p === "states" ? "none" : "states") },
          ].map(({ label, icon: Icon, key, onClick }) => (
            <button
              key={key}
              onClick={onClick}
              className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 transition-all"
              style={{
                fontSize: 13, fontWeight: 500,
                background: panel === key ? "rgba(99,102,241,0.15)" : cardBg,
                border: `1px solid ${panel === key ? "rgba(99,102,241,0.4)" : borderColor}`,
                color: panel === key ? "#818cf8" : textMuted,
                cursor: "pointer",
              }}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className={cn(
        "absolute top-0 right-0 h-full w-[380px] z-20",
        "transform transition-transform duration-300 ease-out",
        panelOpen ? "translate-x-0" : "translate-x-full",
      )}
        style={{ background: panelBg, borderLeft: `1px solid ${borderColor}` }}
      >
        {panel === "transition" && editing && (
          <TransPanel t={editing} isNew={!selEdgeId} intents={intents} actions={actions}
            customSkills={customSkills} allStates={fsmStates} onChange={applyEdit}
            onSave={saveTrans} onDelete={deleteTrans} onClose={closePanel} />
        )}
        {panel === "intents" && (
          <IntentPanel tenantId={tenantId} intents={intents} onClose={closePanel} />
        )}
        {panel === "states" && (
          <StatesPanel tenantId={tenantId} states={fsmStates} onClose={closePanel} />
        )}
      </div>
    </div>
  );
}

function TransPanel({ t, isNew, intents, actions, customSkills, allStates, onChange, onSave, onDelete, onClose }: {
  t: EditTrans; isNew: boolean;
  intents: IntentDefinition[]; actions: ActionCatalogItem[]; customSkills: SkillConfig[];
  allStates: { key: string; label: string }[];
  onChange: (t: EditTrans) => void; onSave: () => void; onDelete: () => void; onClose: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: actColor(t.action) + "15" }}>
            <ArrowRight className="h-4 w-4" style={{ color: actColor(t.action) }} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{isNew ? "New Transition" : "Edit Transition"}</h3>
            <p className="text-[11px] text-muted-foreground">{isNew ? "Define how the conversation flows" : "Changes update live on the canvas"}</p>
          </div>
        </div>
        <button onClick={onClose} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        <Section title="Route">
          <FG label="From State" hint="(Any = global)">
            <Select value={t.fromState || FROM_ANY} onValueChange={(v) => onChange({ ...t, fromState: v === FROM_ANY ? "" : v })}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={FROM_ANY}><span className="text-amber-600 font-medium">{"\u2605"} Any State</span></SelectItem>
                {allStates.map((s) => <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FG>
          <div className="flex items-center justify-center text-muted-foreground/50"><ChevronDown className="h-4 w-4" /></div>
          <FG label="To State">
            <Select value={t.to_state || ""} onValueChange={(v) => onChange({ ...t, to_state: v })}>
              <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Select target…" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__same__"><div className="flex items-center gap-2"><Undo2 className="h-3 w-3 text-muted-foreground" /><span className="text-muted-foreground">Same State</span></div></SelectItem>
                {allStates.map((s) => <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FG>
        </Section>

        <Section title="When">
          <FG label="Intent detected" hint="(blank = any)">
            <Select value={t.intent || INTENT_WILDCARD} onValueChange={(v) => onChange({ ...t, intent: v === INTENT_WILDCARD ? "" : v })}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={INTENT_WILDCARD}><span className="text-muted-foreground">Any intent (wildcard)</span></SelectItem>
                {intents.map((i) => <SelectItem key={i.key} value={i.key}>{i.name ?? i.key}</SelectItem>)}
              </SelectContent>
            </Select>
          </FG>
        </Section>

        <Section title="Then">
          <FG label="Execute action">
            <Select value={t.action} onValueChange={(v) => onChange({ ...t, action: v })}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(actions.length > 0 ? actions.map((a) => a.key) : Object.keys(ACTION_LABELS)).map((a) => (
                  <SelectItem key={a} value={a}>
                    <div className="flex items-center gap-2">
                      <div className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: ACTION_COLORS[a] ?? "#94a3b8" }} />
                      {ACTION_LABELS[a] ?? a}
                    </div>
                  </SelectItem>
                ))}
                {customSkills.length > 0 && (
                  <>
                    <div className="px-3 pt-3 pb-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest border-t mt-1">Custom Personas</div>
                    {customSkills.map((sk) => (
                      <SelectItem key={sk.action} value={sk.action}>
                        <div className="flex items-center gap-2">
                          <div className="h-2.5 w-2.5 rounded-full shrink-0 bg-rose-500" />
                          {sk.name ?? sk.action.replace("conversational__", "").replace(/_/g, " ")}
                        </div>
                      </SelectItem>
                    ))}
                  </>
                )}
              </SelectContent>
            </Select>
          </FG>
          {t.action === "static_reply" && (
            <FG label="Message text">
              <Input className="text-sm h-9" placeholder="Type the static message\u2026" value={t.static_message ?? ""}
                onChange={(e) => onChange({ ...t, static_message: e.target.value })} />
            </FG>
          )}
        </Section>

        <Section title="Bot Message" initClosed>
          <FG label="Prompt" hint="Sent before the action response">
            <Textarea className="text-sm resize-none min-h-[80px]"
              placeholder="e.g. Hello! Welcome"
              value={t.bot_prompt ?? ""} onChange={(e) => onChange({ ...t, bot_prompt: e.target.value })} />
          </FG>
        </Section>

        <Section title="Quick Replies" initClosed>
          <div className="space-y-2">
            {(t.suggested_replies ?? []).map((r, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input className="text-xs h-8 flex-1" placeholder={`Reply ${i + 1}\u2026`} value={r}
                  onChange={(e) => { const n = [...(t.suggested_replies ?? [])]; n[i] = e.target.value; onChange({ ...t, suggested_replies: n }); }} />
                <button onClick={() => onChange({ ...t, suggested_replies: (t.suggested_replies ?? []).filter((_, j) => j !== i) })}
                  className="p-1 rounded text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors"><X className="h-3 w-3" /></button>
              </div>
            ))}
            <button onClick={() => onChange({ ...t, suggested_replies: [...(t.suggested_replies ?? []), ""] })}
              className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors">
              <Plus className="h-3 w-3" />Add reply chip
            </button>
          </div>
        </Section>

        <div className="flex items-center justify-between py-2">
          <Label className="text-sm text-foreground">Enabled</Label>
          <Switch checked={t.enabled} onCheckedChange={(v) => onChange({ ...t, enabled: v })} />
        </div>
      </div>

      <div className="p-4 border-t border-border flex items-center gap-2">
        <Button size="sm" className="flex-1 h-10 font-medium rounded-xl" onClick={onSave}>
          {isNew ? <><Plus className="h-4 w-4 mr-1.5" />Add Transition</> : <><Save className="h-4 w-4 mr-1.5" />Done</>}
        </Button>
        {!isNew && (
          <Button size="sm" variant="outline" className="h-10 w-10 p-0 rounded-xl border-red-200 text-red-500 hover:bg-red-500/10 hover:border-red-300"
            onClick={onDelete} title="Delete transition"><Trash2 className="h-4 w-4" /></Button>
        )}
      </div>
    </div>
  );
}

function IntentPanel({ tenantId, intents, onClose }: { tenantId: string; intents: IntentDefinition[]; onClose: () => void }) {
  const createIntent = useCreateIntent(tenantId);
  const updateIntent = useUpdateIntent(tenantId);
  const deleteIntent = useDeleteIntent(tenantId);
  const [mode, setMode] = useState<null | "new" | string>(null);
  const [draft, setDraft] = useState<Partial<IntentDefinition>>({});
  const isPending = createIntent.isPending || updateIntent.isPending;

  function openNew() { setDraft({ key: "", name: "", description: "", examples: [], enabled: true, priority: 50 }); setMode("new"); }
  function openEdit(i: IntentDefinition) { setDraft({ ...i }); setMode(i.key); }

  async function handleSave() {
    if (mode === "new") {
      if (!draft.key?.trim()) return;
      await createIntent.mutateAsync({ key: draft.key.trim().toLowerCase().replace(/\s+/g, "_"), name: draft.name?.trim() || draft.key.trim(), description: draft.description?.trim() || "", examples: draft.examples ?? [], enabled: draft.enabled ?? true, priority: draft.priority ?? 50 });
      toast.success("Intent created");
    } else {
      await updateIntent.mutateAsync({ key: mode as string, updates: draft });
      toast.success("Intent updated");
    }
    setMode(null);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-violet-500/10 flex items-center justify-center"><Brain className="h-4 w-4 text-violet-500" /></div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{mode === null ? "Intents" : mode === "new" ? "New Intent" : "Edit Intent"}</h3>
            <p className="text-[11px] text-muted-foreground">{mode === null ? `${intents.length} intent${intents.length !== 1 ? "s" : ""} configured` : "Define when this intent triggers"}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {mode !== null && <button onClick={() => setMode(null)} className="rounded-lg px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">{"\u2190"} Back</button>}
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><X className="h-4 w-4" /></button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {mode === null && (
          <div className="p-4 space-y-2">
            <button onClick={openNew} className="w-full flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-primary/20 text-primary hover:border-primary/40 hover:bg-primary/5 transition-all py-3 text-sm font-medium">
              <Plus className="h-4 w-4" />New Intent
            </button>
            {intents.length === 0 && <p className="text-xs text-muted-foreground text-center py-6">No intents configured yet.</p>}
            {intents.map((intent) => (
              <button key={intent.key} onClick={() => openEdit(intent)} className="w-full text-left rounded-xl border border-border hover:border-primary/30 hover:bg-primary/[.02] transition-all p-3.5 group">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-foreground truncate">{intent.name ?? intent.key}</div>
                    <div className="text-[10px] font-mono text-muted-foreground mt-0.5">{intent.key}</div>
                    {intent.description && <div className="text-[11px] text-muted-foreground mt-1.5 line-clamp-2 leading-relaxed">{intent.description}</div>}
                  </div>
                  <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Edit className="h-3.5 w-3.5 text-muted-foreground" />
                    <button onClick={(e) => { e.stopPropagation(); deleteIntent.mutate(intent.key); }} className="p-1 rounded text-muted-foreground/50 hover:text-red-500 hover:bg-red-500/10 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
        {mode !== null && (
          <div className="p-5 space-y-4">
            {mode === "new" && (
              <FG label="Key" hint="(slug, e.g. ask_price)">
                <Input className="text-sm h-9 font-mono" placeholder="ask_availability" value={draft.key ?? ""} autoFocus
                  onChange={(e) => setDraft((d) => ({ ...d, key: e.target.value.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "") }))} />
              </FG>
            )}
            {mode !== "new" && <div className="rounded-lg bg-muted px-3 py-2 text-xs font-mono text-muted-foreground">{mode}</div>}
            <FG label="Display Name"><Input className="text-sm h-9" placeholder="Ask about availability" value={draft.name ?? ""} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} /></FG>
            <FG label="Description" hint="Detection instructions for the LLM">
              <Textarea className="text-sm resize-none min-h-[100px]" placeholder="Describe when this intent should trigger\u2026"
                value={draft.description ?? ""} onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))} />
            </FG>
          </div>
        )}
      </div>

      {mode !== null && (
        <div className="p-4 border-t border-border flex items-center gap-2">
          <Button size="sm" className="flex-1 h-10 font-medium rounded-xl" onClick={handleSave} disabled={isPending || (mode === "new" && !draft.key?.trim())}>
            <Save className="h-4 w-4 mr-1.5" />{isPending ? "Saving\u2026" : mode === "new" ? "Create Intent" : "Save Changes"}
          </Button>
          <Button size="sm" variant="outline" className="h-10 rounded-xl" onClick={() => setMode(null)}>Cancel</Button>
        </div>
      )}
    </div>
  );
}

function StatesPanel({ tenantId, states, onClose }: { tenantId: string; states: { key: string; label: string; is_default?: boolean }[]; onClose: () => void }) {
  const createState = useCreateFSMState(tenantId);
  const deleteState = useDeleteFSMState(tenantId);
  const [mode, setMode] = useState<null | "new">(null);
  const [nk, setNK] = useState("");
  const [nl, setNL] = useState("");
  const slug = nk.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);
  const dup = slug ? states.some((s) => s.key === slug) : false;

  async function handleCreate() {
    if (!slug || dup) return;
    await createState.mutateAsync({ key: slug, label: nl.trim() || slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) });
    setNK(""); setNL(""); setMode(null);
    toast.success("State created");
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center"><Layers className="h-4 w-4 text-blue-500" /></div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{mode === "new" ? "New State" : "States"}</h3>
            <p className="text-[11px] text-muted-foreground">{mode === "new" ? "Create a conversation state" : `${states.length} state${states.length !== 1 ? "s" : ""}`}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {mode !== null && <button onClick={() => setMode(null)} className="rounded-lg px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">{"\u2190"} Back</button>}
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><X className="h-4 w-4" /></button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {mode === null && (
          <div className="p-4 space-y-2">
            <button onClick={() => { setNK(""); setNL(""); setMode("new"); }}
              className="w-full flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-primary/20 text-primary hover:border-primary/40 hover:bg-primary/5 transition-all py-3 text-sm font-medium">
              <Plus className="h-4 w-4" />New State
            </button>
            {states.map((s) => {
              const immut = s.key === "idle";
              return (
                <div key={s.key} className={cn("flex items-center justify-between rounded-xl border border-border px-4 py-3 group transition-all", immut ? "opacity-60" : "hover:border-border/80 hover:bg-muted/50")}>
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <Circle className={cn("h-3 w-3 shrink-0", immut ? "fill-primary text-primary" : "fill-muted-foreground/30 text-muted-foreground/30 group-hover:fill-primary group-hover:text-primary transition-colors")} />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">{s.label}</div>
                      <div className="text-[10px] font-mono text-muted-foreground">{s.key}</div>
                    </div>
                  </div>
                  {immut ? (
                    <Badge variant="secondary" className="text-[9px] h-5 px-2">default</Badge>
                  ) : (
                    <button onClick={() => deleteState.mutate(s.key)} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-red-500 hover:bg-red-500/10 transition-all opacity-0 group-hover:opacity-100" title="Delete state"><Trash2 className="h-3.5 w-3.5" /></button>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {mode === "new" && (
          <div className="p-5 space-y-4">
            <FG label="Key" hint="(auto-slugified)">
              <Input className="text-sm h-9 font-mono" placeholder="e.g. upselling" value={nk} onChange={(e) => setNK(e.target.value)} autoFocus />
              {slug && <div className="text-[11px] font-mono text-muted-foreground mt-1">Key: <span className={dup ? "text-red-500" : "text-foreground"}>{slug}</span>{dup && <span className="text-red-500 ml-1">{"\u2014"} already exists</span>}</div>}
            </FG>
            <FG label="Display Label" hint="(optional)">
              <Input className="text-sm h-9" placeholder="Upselling" value={nl} onChange={(e) => setNL(e.target.value)} />
            </FG>
          </div>
        )}
      </div>

      {mode === "new" && (
        <div className="p-4 border-t border-border flex items-center gap-2">
          <Button size="sm" className="flex-1 h-10 font-medium rounded-xl" onClick={handleCreate} disabled={!slug || dup || createState.isPending}>
            <Plus className="h-4 w-4 mr-1.5" />{createState.isPending ? "Creating\u2026" : "Create State"}
          </Button>
          <Button size="sm" variant="outline" className="h-10 rounded-xl" onClick={() => setMode(null)}>Cancel</Button>
        </div>
      )}
    </div>
  );
}

function Section({ title, children, initClosed }: { title: string; children: ReactNode; initClosed?: boolean }) {
  const [closed, setClosed] = useState(initClosed ?? false);
  return (
    <div className="rounded-xl overflow-hidden border border-border">
      <button
        onClick={() => setClosed((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-muted/50 text-muted-foreground"
        style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase" }}
      >
        {title}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200 text-muted-foreground/60", closed && "-rotate-90")} />
      </button>
      {!closed && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </div>
  );
}

function FG({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-medium text-muted-foreground">
        {label}{hint && <span className="ml-1.5 font-normal text-muted-foreground/60">{hint}</span>}
      </Label>
      {children}
    </div>
  );
}
