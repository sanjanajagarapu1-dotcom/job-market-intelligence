"use client";

import { ColumnBars, Donut, HorizontalBars } from "@/components/charts";
import { ErrorMessage, Loading } from "@/components/status";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type NameCount, type Summary, useApi } from "@/lib/api";

const SENIORITY_ORDER = ["Intern", "Entry", "Mid", "Senior", "Lead", "Unknown"];

export default function DashboardPage() {
  const summary = useApi<Summary>("/stats/summary");
  const skills = useApi<NameCount[]>("/stats/top-skills?limit=15");
  const companies = useApi<NameCount[]>("/stats/companies?limit=15");
  const seniority = useApi<NameCount[]>("/stats/seniority");
  const workMode = useApi<NameCount[]>("/stats/work-mode");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Data Job Market Dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Data analyst & data scientist postings, enriched with AI-extracted skills and refreshed daily.
        </p>
      </div>

      {summary.error ? (
        <ErrorMessage message={summary.error} />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Kpi label="Jobs" value={summary.data?.jobs.toLocaleString()} slow={summary.slow} />
          <Kpi label="Companies" value={summary.data?.companies.toLocaleString()} />
          <Kpi
            label="Avg min salary"
            value={summary.data && (summary.data.avg_min_salary ? `$${summary.data.avg_min_salary.toLocaleString()}` : "n/a")}
          />
          <Kpi
            label="Remote"
            value={summary.data && (summary.data.remote_share != null ? `${Math.round(summary.data.remote_share * 100)}%` : "n/a")}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Top 15 in-demand skills" description="Number of postings that ask for each skill" state={skills}>
          {(data) => <HorizontalBars data={data} />}
        </ChartCard>
        <ChartCard title="Companies hiring the most" description="Number of open data roles" state={companies}>
          {(data) => <HorizontalBars data={data} />}
        </ChartCard>
        <ChartCard title="Jobs by seniority" state={seniority}>
          {(data) => <ColumnBars data={data} order={SENIORITY_ORDER} />}
        </ChartCard>
        <ChartCard title="Remote vs hybrid vs onsite" state={workMode}>
          {(data) => <Donut data={data} />}
        </ChartCard>
      </div>
    </div>
  );
}

function Kpi({ label, value, slow }: { label: string; value?: string | null; slow?: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl tabular-nums">{value ?? "…"}</CardTitle>
        {slow && !value && <p className="text-xs text-muted-foreground">Waking up the server…</p>}
      </CardHeader>
    </Card>
  );
}

function ChartCard<T>({
  title,
  description,
  state,
  children,
}: {
  title: string;
  description?: string;
  state: { data: T | null; error: string | null; slow: boolean };
  children: (data: T) => React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        {state.error ? (
          <ErrorMessage message={state.error} />
        ) : state.data ? (
          children(state.data)
        ) : (
          <Loading slow={state.slow} />
        )}
      </CardContent>
    </Card>
  );
}
