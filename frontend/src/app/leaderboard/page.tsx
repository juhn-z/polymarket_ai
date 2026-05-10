import { LeaderboardTable } from "@/components/leaderboard/LeaderboardTable";

export default function LeaderboardPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Leaderboard</h1>
        <p className="text-muted-foreground">Top depositors ranked by profit.</p>
      </header>
      <LeaderboardTable />
    </div>
  );
}
