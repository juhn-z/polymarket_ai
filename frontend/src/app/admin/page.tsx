import { SystemStatus } from "@/components/admin/SystemStatus";
import { AdminActions } from "@/components/admin/AdminActions";

export default function AdminPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Admin</h1>
        <p className="text-muted-foreground">Trigger pipeline steps manually and pause/resume the system.</p>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        <SystemStatus />
        <AdminActions />
      </div>
    </div>
  );
}
