import { StatsCards } from "@/components/dashboard/StatsCards";
import { TodayPrediction } from "@/components/dashboard/TodayPrediction";
import { PnLChart } from "@/components/dashboard/PnLChart";
import { RecentTrades } from "@/components/dashboard/RecentTrades";

export default function DashboardPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">AI-driven Polymarket prediction vault</p>
      </header>
      <StatsCards />
      <TodayPrediction />
      <div className="grid gap-4 md:grid-cols-3">
        <PnLChart />
        <RecentTrades />
      </div>
    </div>
  );
}
