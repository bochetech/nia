"use client";

import { use, useMemo, useState } from "react";
import { useSkills, useUpsertSkill, useDeleteSkill, useActions } from "@/hooks/use-api";
import type { SkillConfig } from "@/lib/api";
import { ACTION_LABELS, ACTION_COLORS } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Plus, Trash2, Save, ChevronRight, MessageSquare, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useForm, useFieldArray } from "react-hook-form";

// ─── Constants ─────────────────────────────────────────────────

const BUILTIN_ACTIONS = [
  "faq",
  "recommend",
  "handoff",
  "nps",
  "complaint",
  "static_reply",
  "discovery",
  "conversational",
];

const ACTION_DESCRIPTIONS: Record<string, string> = {
  faq: "Answers questions using the RAG knowledge base via semantic search.",
  recommend: "Suggests products or services based on user needs.",
  handoff: "Transfers the conversation to a human agent.",
  nps: "Collects a Net Promoter Score from the user.",
  complaint: "Handles complaints and escalation flows.",
  static_reply: "Sends a predefined static text response.",
  discovery: "Asks clarifying questions to understand user intent.",
  conversational: "Pure LLM response driven by your custom system prompt — no external services required.",
};

const CONVERSATIONAL_COLOR = "#FF2D55";

/** Convert a display name to a safe slug: "Guía Turismo" → "guia_turismo" */
function toSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

// ─── Page ──────────────────────────────────────────────────────

export default function SkillsPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const { data: skillsData, isLoading } = useSkills(tenantId);
  const { data: actionsData } = useActions(tenantId);
  const upsert = useUpsertSkill(tenantId);

  const [selectedAction, setSelectedAction] = useState<string>("faq");
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [newSkillName, setNewSkillName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const skills: Record<string, SkillConfig> = useMemo(() => {
    const arr: SkillConfig[] = skillsData?.data ?? [];
    return arr.reduce<Record<string, SkillConfig>>((acc, s) => {
      acc[s.action] = s;
      return acc;
    }, {});
  }, [skillsData]);

  // Builtin catalog actions (from API or fallback)
  const catalogActions: string[] =
    (actionsData?.data?.map((a: any) => a.key ?? a.action) ?? BUILTIN_ACTIONS)
      .filter((a: string) => !a.startsWith("conversational__"));

  // Custom conversational sub-skills (persisted in DB with action = "conversational__slug")
  const customConversational: SkillConfig[] = useMemo(() => {
    const arr: SkillConfig[] = skillsData?.data ?? [];
    return arr
      .filter((s) => s.action.startsWith("conversational__"))
      .sort((a, b) => (a.name ?? a.action).localeCompare(b.name ?? b.action));
  }, [skillsData]);

  const newSlug = toSlug(newSkillName);
  const newActionKey = newSlug ? `conversational__${newSlug}` : "";
  const slugConflict = newSlug ? !!skills[newActionKey] : false;

  async function handleCreateCustomSkill() {
    if (!newSlug || slugConflict) return;
    await upsert.mutateAsync({
      actionKey: newActionKey,
      skill: {
        action: newActionKey,
        name: newSkillName.trim(),
        description: "Custom conversational skill with a dedicated system prompt.",
        enabled: true,
        preparation_prompt: "",
        entity_schema: [],
        response_templates: {},
      },
    });
    setShowNewDialog(false);
    setNewSkillName("");
    setSelectedAction(newActionKey);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
        <span className="ml-2 text-sm text-muted-foreground">Loading skills…</span>
      </div>
    );
  }

  const currentSkill = skills[selectedAction] ?? {
    action: selectedAction,
    enabled: true,
    entity_schema: [],
    preparation_prompt: "",
    response_templates: {},
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* ── Sidebar ──────────────────────────────────────── */}
      <div className="w-60 border-r bg-[#f5f5f7] flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* Built-in skills */}
          <div>
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5 px-1">
              Built-in Skills
            </div>
            <div className="space-y-0.5">
              {catalogActions.map((action: string) => {
                const hasConfig = !!skills[action];
                return (
                  <button
                    key={action}
                    onClick={() => setSelectedAction(action)}
                    className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] transition-all duration-150 ${
                      selectedAction === action
                        ? "bg-white border border-black/[0.04] shadow-apple-sm font-medium"
                        : "hover:bg-white/60"
                    }`}
                  >
                    <div
                      className="h-2.5 w-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: ACTION_COLORS[action] ?? "#8E8E93" }}
                    />
                    <span className="flex-1 truncate">{ACTION_LABELS[action] ?? action}</span>
                    {hasConfig && (
                      <div className="h-1.5 w-1.5 rounded-full bg-[#34C759] shrink-0" title="Configured" />
                    )}
                    {selectedAction === action && (
                      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Custom conversational skills */}
          <div>
            <div className="flex items-center justify-between mb-1.5 px-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Custom Personas
              </span>
              <button
                onClick={() => setShowNewDialog(true)}
                className="h-5 w-5 rounded flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-background transition-colors"
                title="New conversational skill"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>

            {customConversational.length === 0 ? (
              <button
                onClick={() => setShowNewDialog(true)}
                className="w-full rounded-xl border border-dashed border-[#FF2D55]/20 bg-[#FF2D55]/5 py-3 px-2 text-center text-xs text-[#FF2D55] hover:bg-[#FF2D55]/10 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5 mx-auto mb-1 opacity-70" />
                Create your first persona
              </button>
            ) : (
              <div className="space-y-0.5">
                {customConversational.map((skill) => (
                  <button
                    key={skill.action}
                    onClick={() => setSelectedAction(skill.action)}
                    className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] transition-all duration-150 group ${
                      selectedAction === skill.action
                        ? "bg-white border border-black/[0.04] shadow-apple-sm font-medium"
                        : "hover:bg-white/60"
                    }`}
                  >
                    <MessageSquare
                      className="h-3 w-3 shrink-0"
                      style={{ color: CONVERSATIONAL_COLOR }}
                    />
                    <span className="flex-1 truncate">{skill.name ?? skill.action}</span>
                    {selectedAction === skill.action && (
                      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Main editor ──────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-6">
        <SkillEditor
          key={selectedAction}
          tenantId={tenantId}
          action={selectedAction}
          skill={currentSkill}
          onDeleteRequest={
            selectedAction.startsWith("conversational__")
              ? () => setDeleteTarget(selectedAction)
              : undefined
          }
        />
      </div>

      {/* ── New persona dialog ───────────────────────────── */}
      <Dialog open={showNewDialog} onOpenChange={setShowNewDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#FF2D55]" />
              New Custom Persona
            </DialogTitle>
            <DialogDescription>
              Create a new conversational skill with its own system prompt. It will appear
              as a selectable action in the FSM transition editor.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="skill-name">Display Name</Label>
              <Input
                id="skill-name"
                autoFocus
                placeholder="e.g. Guía de Turismo, Sales Assistant…"
                value={newSkillName}
                onChange={(e) => setNewSkillName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateCustomSkill()}
              />
            </div>
            {newSlug && (
              <div className="rounded-md bg-muted px-3 py-2 text-xs font-mono text-muted-foreground">
                Action key:{" "}
                <span className={slugConflict ? "text-destructive" : "text-foreground"}>
                  conversational__{newSlug}
                </span>
                {slugConflict && (
                  <span className="ml-2 text-destructive font-normal">(already exists)</span>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowNewDialog(false); setNewSkillName(""); }}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateCustomSkill}
              disabled={!newSlug || slugConflict || upsert.isPending}
              loading={upsert.isPending}
            >
              <Plus className="h-4 w-4 mr-1.5" />
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete confirm ───────────────────────────────── */}
      <DeleteSkillDialog
        tenantId={tenantId}
        actionKey={deleteTarget}
        skillName={deleteTarget ? (skills[deleteTarget]?.name ?? deleteTarget) : ""}
        onClose={(deleted) => {
          setDeleteTarget(null);
          if (deleted) setSelectedAction("faq");
        }}
      />
    </div>
  );
}

// ─── Delete confirm dialog ─────────────────────────────────────

function DeleteSkillDialog({
  tenantId,
  actionKey,
  skillName,
  onClose,
}: {
  tenantId: string;
  actionKey: string | null;
  skillName: string;
  onClose: (deleted: boolean) => void;
}) {
  const deleteSkill = useDeleteSkill(tenantId);

  async function handleDelete() {
    if (!actionKey) return;
    await deleteSkill.mutateAsync(actionKey);
    onClose(true);
  }

  return (
    <AlertDialog open={!!actionKey} onOpenChange={(open: boolean) => !open && onClose(false)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete "{skillName}"?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently remove this custom persona and its system prompt.
            Any FSM transitions using this action will stop working until reassigned.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={handleDelete}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// ─── Skill editor ──────────────────────────────────────────────

function SkillEditor({
  tenantId,
  action,
  skill,
  onDeleteRequest,
}: {
  tenantId: string;
  action: string;
  skill: SkillConfig;
  onDeleteRequest?: () => void;
}) {
  const upsert = useUpsertSkill(tenantId);
  const isCustomConversational = action.startsWith("conversational__");
  const isConversational = action === "conversational" || isCustomConversational;

  // Display name: for custom skills use the stored name, for builtins use ACTION_LABELS
  const displayName = isCustomConversational
    ? (skill.name ?? action.replace("conversational__", "").replace(/_/g, " "))
    : (ACTION_LABELS[action] ?? action);

  const form = useForm({
    defaultValues: {
      name: skill.name ?? displayName,
      preparation_prompt: skill.preparation_prompt ?? "",
      entity_schema: skill.entity_schema ?? [],
      response_templates: Object.entries(skill.response_templates ?? {}).map(
        ([key, value]) => ({ key, value: value as string })
      ),
    },
  });

  const { fields: entityFields, append: appendEntity, remove: removeEntity } =
    useFieldArray({ control: form.control, name: "entity_schema" });

  const { fields: templateFields, append: appendTemplate, remove: removeTemplate } =
    useFieldArray({ control: form.control, name: "response_templates" });

  const onSubmit = form.handleSubmit(async (values) => {
    const templates: Record<string, string> = {};
    values.response_templates.forEach(({ key, value }) => {
      if (key.trim()) templates[key.trim()] = value;
    });

    await upsert.mutateAsync({
      actionKey: action,
      skill: {
        action,
        name: isCustomConversational ? (values.name || displayName) : (ACTION_LABELS[action] ?? action),
        description: isCustomConversational
          ? "Custom conversational skill with a dedicated system prompt."
          : (ACTION_DESCRIPTIONS[action] ?? ""),
        enabled: true,
        preparation_prompt: values.preparation_prompt,
        entity_schema: values.entity_schema,
        response_templates: templates,
      },
    });
    toast.success("Skill saved");
  });

  const accentColor = isCustomConversational
    ? CONVERSATIONAL_COLOR
    : (ACTION_COLORS[action] ?? "#8E8E93");

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="h-10 w-10 rounded-xl flex items-center justify-center text-white text-sm font-semibold shrink-0 shadow-apple-sm"
          style={{ backgroundColor: accentColor }}
        >
          {isCustomConversational
            ? <MessageSquare className="h-5 w-5" />
            : displayName.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold tracking-tight truncate">{displayName}</h1>
          <p className="text-sm text-muted-foreground truncate">
            {isCustomConversational
              ? <span className="font-mono text-xs">{action}</span>
              : (ACTION_DESCRIPTIONS[action] ?? "Configure this skill")}
          </p>
        </div>
        {onDeleteRequest && (
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:bg-destructive/10 hover:text-destructive border-destructive/30 shrink-0"
            onClick={onDeleteRequest}
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Delete
          </Button>
        )}
      </div>

      <form onSubmit={onSubmit} className="space-y-5">
        {/* Custom name field — only for conversational__ skills */}
        {isCustomConversational && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Persona Name</CardTitle>
              <CardDescription>
                Display name shown in the FSM editor action selector and in logs.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Input
                placeholder="e.g. Guía de Turismo, Sales Assistant…"
                {...form.register("name")}
              />
            </CardContent>
          </Card>
        )}

        {/* System / Preparation Prompt */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {isConversational ? "System Prompt" : "Preparation Prompt"}
            </CardTitle>
            <CardDescription>
              {isConversational
                ? "This is the full system prompt the LLM receives when this skill runs. Define the persona's character, tone, scope, and constraints here."
                : <>Additional context injected into the LLM prompt when this skill is active. Use <code className="text-xs bg-muted px-1 rounded">{"{{entity}}"}</code> placeholders.</>}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isConversational && (
              <div className="rounded-xl border border-[#FF2D55]/15 bg-[#FF2D55]/5 px-3 py-2.5 text-xs text-[#FF2D55] leading-relaxed">
                <strong>💬 Conversational skill</strong> — the LLM responds freely using only this system prompt
                and the conversation history. No external services are called.
                {isCustomConversational && (
                  <> This is an <strong>independent persona</strong> — changing it won't affect the default <em>Conversational</em> skill.</>
                )}
              </div>
            )}
            <Textarea
              rows={isConversational ? 10 : 5}
              placeholder={
                isConversational
                  ? "Eres un asistente experto en turismo de aventura. Responde siempre en español, con un tono entusiasta y amigable. Ayuda al usuario a planificar su viaje ideal y a descubrir destinos únicos. No respondas preguntas que no estén relacionadas con viajes."
                  : "You are helping the user with… Always respond in a friendly tone…"
              }
              {...form.register("preparation_prompt")}
            />
          </CardContent>
        </Card>

        {/* Entity Schema */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Entity Schema</CardTitle>
                <CardDescription>
                  Fields the LLM should extract from user messages for this skill.
                </CardDescription>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() =>
                  appendEntity({
                    name: "",
                    type: "string",
                    description: "",
                    required: false,
                    enum_values: [],
                    examples: [],
                  })
                }
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Field
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {entityFields.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-3">
                No entities defined. This skill won't extract any structured data.
              </p>
            ) : (
              <div className="space-y-3">
                {entityFields.map((field, idx) => (
                  <EntityFieldRow
                    key={field.id}
                    idx={idx}
                    register={form.register}
                    onRemove={() => removeEntity(idx)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Response Templates */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Response Templates</CardTitle>
                <CardDescription>
                  Named templates the LLM can choose from. Key = template ID, Value = text.
                </CardDescription>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => appendTemplate({ key: "", value: "" })}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add Template
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {templateFields.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-3">
                No templates yet. The LLM will generate responses freely.
              </p>
            ) : (
              <div className="space-y-3">
                {templateFields.map((field, idx) => (
                  <div key={field.id} className="flex gap-2 items-start">
                    <Input
                      className="w-32 shrink-0 font-mono text-xs h-9"
                      placeholder="template_id"
                      {...form.register(`response_templates.${idx}.key`)}
                    />
                    <Textarea
                      rows={2}
                      className="flex-1 text-xs"
                      placeholder="Template text…"
                      {...form.register(`response_templates.${idx}.value`)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeTemplate(idx)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" loading={upsert.isPending}>
            <Save className="h-4 w-4 mr-1.5" />
            Save Skill
          </Button>
        </div>
      </form>
    </div>
  );
}

// ─── Entity field row ──────────────────────────────────────────

function EntityFieldRow({
  idx,
  register,
  onRemove,
}: {
  idx: number;
  register: any;
  onRemove: () => void;
}) {
  const TYPES = ["string", "number", "boolean", "enum", "date"];

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex-1 grid grid-cols-3 gap-2">
          <div>
            <Label className="text-[10px] text-muted-foreground">Name</Label>
            <Input
              className="h-7 text-xs font-mono"
              placeholder="field_name"
              {...register(`entity_schema.${idx}.name`)}
            />
          </div>
          <div>
            <Label className="text-[10px] text-muted-foreground">Type</Label>
            <Input
              className="h-7 text-xs"
              list={`types-${idx}`}
              placeholder="string"
              {...register(`entity_schema.${idx}.type`)}
            />
            <datalist id={`types-${idx}`}>
              {TYPES.map((t) => <option key={t} value={t} />)}
            </datalist>
          </div>
          <div>
            <Label className="text-[10px] text-muted-foreground">Description</Label>
            <Input
              className="h-7 text-xs"
              placeholder="What this field means…"
              {...register(`entity_schema.${idx}.description`)}
            />
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 mt-4 shrink-0 text-muted-foreground hover:text-destructive"
          onClick={onRemove}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
      <div>
        <Label className="text-[10px] text-muted-foreground">
          Enum values <span className="font-normal">(comma-separated, optional)</span>
        </Label>
        <Input
          className="h-7 text-xs font-mono"
          placeholder="option_a, option_b, option_c"
          {...register(`entity_schema.${idx}.enum_values`)}
        />
      </div>
    </div>
  );
}

