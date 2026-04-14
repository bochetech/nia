import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
