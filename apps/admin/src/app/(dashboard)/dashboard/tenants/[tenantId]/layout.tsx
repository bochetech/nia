import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";

export default async function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tenantId: string }>;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  // tenantId is available for future use (e.g. breadcrumbs via server context)
  await params;

  return <>{children}</>;
}
