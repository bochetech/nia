"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateTenant } from "@/hooks/use-api";
import { useState } from "react";

const schema = z.object({
  id: z
    .string()
    .min(3)
    .max(50)
    .regex(/^[a-z0-9_]+$/, "Only lowercase letters, numbers and underscores"),
  name: z.string().min(2).max(200),
  contact_email: z.string().email(),
  plan: z.enum(["starter", "professional", "enterprise"]),
});

type FormData = z.infer<typeof schema>;

export function CreateTenantDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const createTenant = useCreateTenant();
  const [apiKey, setApiKey] = useState("");

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { plan: "starter" },
  });

  const onSubmit = async (data: FormData) => {
    const result = await createTenant.mutateAsync(data);
    if (result.data.api_key) {
      setApiKey(result.data.api_key);
    }
  };

  const handleClose = () => {
    reset();
    setApiKey("");
    onClose();
  };

  if (apiKey) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Tenant Created ✓</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Copy this API key — it will only be shown once.
            </p>
            <div className="rounded-md bg-muted px-3 py-2 font-mono text-xs break-all select-all">
              {apiKey}
            </div>
          </div>
          <DialogFooter>
            <Button onClick={handleClose}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Tenant</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label>Tenant ID</Label>
            <Input
              placeholder="my_tenant"
              {...register("id")}
            />
            {errors.id && (
              <p className="text-xs text-destructive">{errors.id.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input placeholder="My Company Assistant" {...register("name")} />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Contact Email</Label>
            <Input
              type="email"
              placeholder="admin@company.com"
              {...register("contact_email")}
            />
            {errors.contact_email && (
              <p className="text-xs text-destructive">{errors.contact_email.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Plan</Label>
            <Select
              defaultValue="starter"
              onValueChange={(v) => setValue("plan", v as FormData["plan"])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="professional">Professional</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create Tenant
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
