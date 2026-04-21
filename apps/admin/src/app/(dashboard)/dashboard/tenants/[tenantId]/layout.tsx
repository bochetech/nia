import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { TenantHeader } from "@/components/layout/tenant-header";

export default async function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tenantId: string }>;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  const { tenantId } = await params;

  return (
    <div className="flex flex-col h-full">
      <TenantHeader tenantId={tenantId} />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
