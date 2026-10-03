"use client";

import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { NameCount } from "@/lib/api";

export const BRAND = "#2563eb";
const PIE_COLORS = ["#2563eb", "#60a5fa", "#f97316", "#a3a3a3", "#10b981"];

/** Horizontal bar chart: one bar per item, biggest on top. */
export function HorizontalBars({ data, height = 380 }: { data: NameCount[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <XAxis type="number" tick={{ fontSize: 12 }} allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} interval={0} />
        <Tooltip formatter={(v) => [v, "Job postings"]} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
        <Bar dataKey="count" fill={BRAND} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Vertical bar chart in a fixed category order (e.g. seniority levels). */
export function ColumnBars({ data, order }: { data: NameCount[]; order?: string[] }) {
  const sorted = order
    ? order.map((name) => data.find((d) => d.name === name)).filter((d): d is NameCount => !!d)
    : data;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={sorted} margin={{ right: 16 }}>
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
        <Tooltip formatter={(v) => [v, "Job postings"]} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
        <Bar dataKey="count" fill={BRAND} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({ data }: { data: NameCount[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="name" innerRadius={70} outerRadius={110} paddingAngle={2}>
          {data.map((d, i) => (
            <Cell key={d.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v, name) => [v, name]} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
