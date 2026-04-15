import { redirect } from "next/navigation";

/**
 * /dashboard/tenants → redirect to /dashboard
 * The overview page already shows the full tenant list,
 * so this route just avoids a 404.
 */
export default function TenantsPage() {
  redirect("/dashboard");
}
