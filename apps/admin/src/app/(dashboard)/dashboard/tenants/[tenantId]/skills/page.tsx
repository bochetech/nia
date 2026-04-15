"use client";

import { use, useMemo, useState } from "react";
import { useSkills, useUpsertSkill, useActions } from "@/hooks/use-api";
import type { SkillConfig } from "@/lib/api";
import { ACTION_LABELS, ACTION_COLORS } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Plus, Trash2, Save, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useForm, useFieldArray } from "react-hook-form";

const DEFAULT_ACTIONS = [
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

export default function SkillsPage({
  params,
}: {
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const { data: skillsData, isLoading } = useSkills(tenantId);
  const { data: actionsData } = useActions(tenantId);
  const [selectedAction, setSelectedAction] = useState<string>("faq");

  const skills: Record<string, SkillConfig> = useMemo(() => {
    const arr: SkillConfig[] = skillsData?.data ?? [];
    return arr.reduce<Record<string, SkillConfig>>((acc, s) => {
      acc[s.action] = s;
      return acc;
    }, {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skillsData]);
  const catalogActions = actionsData?.data?.map((a: any) => a.key ?? a.action) ?? DEFAULT_ACTIONS;

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="text-muted-foreground text-sm">Loading skills…</div>
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
      {/* ── Sidebar: action list ────────────────────────── */}
      <div className="w-56 border-r bg-muted/30 p-3 flex flex-col gap-1 overflow-y-auto">
        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 px-1">
          Actions
        </div>
        {catalogActions.map((action: string) => {
          const hasConfig = !!skills[action];
          return (
            <button
              key={action}
              onClick={() => setSelectedAction(action)}
              className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                selectedAction === action
                  ? "bg-background border shadow-sm font-medium"
                  : "hover:bg-background/60"
              }`}
            >
              <div
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: ACTION_COLORS[action] ?? "#94a3b8" }}
              />
              <span className="flex-1">{ACTION_LABELS[action] ?? action}</span>
              {hasConfig && (
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 shrink-0" title="Configured" />
              )}
              {selectedAction === action && (
                <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Main: skill editor ──────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-6">
        <SkillEditor
          key={selectedAction}
          tenantId={tenantId}
          action={selectedAction}
          skill={currentSkill}
        />
      </div>
    </div>
  );
}

// ─── Skill editor ──────────────────────────────────────────────

function SkillEditor({
  tenantId,
  action,
  skill,
}: {
  tenantId: string;
  action: string;
  skill: SkillConfig;
}) {
  const upsert = useUpsertSkill(tenantId);

  const form = useForm({
    defaultValues: {
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
        name: ACTION_LABELS[action] ?? action,
        description: ACTION_DESCRIPTIONS[action] ?? "",
        enabled: true,
        preparation_prompt: values.preparation_prompt,
        entity_schema: values.entity_schema,
        response_templates: templates,
      },
    });
    toast.success("Skill saved");
  });

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="h-10 w-10 rounded-xl flex items-center justify-center text-white text-sm font-bold"
          style={{ backgroundColor: ACTION_COLORS[action] ?? "#94a3b8" }}
        >
          {(ACTION_LABELS[action] ?? action).charAt(0).toUpperCase()}
        </div>
        <div>
          <h1 className="text-xl font-bold">{ACTION_LABELS[action] ?? action}</h1>
          <p className="text-sm text-muted-foreground">{ACTION_DESCRIPTIONS[action] ?? "Configure this skill"}</p>
        </div>
      </div>

      <form onSubmit={onSubmit} className="space-y-5">
        {/* Preparation Prompt */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {action === "conversational" ? "System Prompt" : "Preparation Prompt"}
            </CardTitle>
            <CardDescription>
              {action === "conversational"
                ? "This is the full system prompt the LLM receives when this skill runs. Define the bot's persona, tone, and scope here."
                : "Additional context injected into the LLM prompt when this skill is active. Use "}{" "}
              {action !== "conversational" && (
                <code className="text-xs bg-muted px-1 rounded">{"{{entity}}"}</code>
              )}
              {action !== "conversational" && " placeholders."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {action === "conversational" && (
              <div className="rounded-lg border border-pink-200 bg-pink-50 px-3 py-2.5 text-xs text-pink-700 leading-relaxed">
                <strong>💬 Conversational skill</strong> — the LLM responds freely using only this system prompt and the conversation history.
                No external services are called. Perfect for custom personas, role-plays, or specialized mini-assistants.
              </div>
            )}
            <Textarea
              rows={action === "conversational" ? 8 : 5}
              placeholder={
                action === "conversational"
                  ? "Eres un asistente experto en turismo de aventura. Responde siempre en español, con un tono entusiasta y amigable. Ayuda al usuario a planificar su viaje ideal…"
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
