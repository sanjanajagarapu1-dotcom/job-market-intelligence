"use client";

import { useState } from "react";

import { ErrorMessage, Loading } from "@/components/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type JobList, useApi } from "@/lib/api";

const PAGE_SIZE = 25;
const SENIORITY = ["Intern", "Entry", "Mid", "Senior", "Lead"];
const WORK_MODES = ["Remote", "Hybrid", "Onsite"];

export default function JobsPage() {
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [seniority, setSeniority] = useState("");
  const [workMode, setWorkMode] = useState("");
  const [page, setPage] = useState(0);

  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
  if (search) params.set("search", search);
  if (seniority) params.set("seniority", seniority);
  if (workMode) params.set("work_mode", workMode);
  const { data, error, slow } = useApi<JobList>(`/jobs?${params}`);

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Job Explorer</h1>
        <p className="mt-1 text-muted-foreground">Search by title, company or skill, newest first.</p>
      </div>

      <form
        className="flex flex-wrap gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(draft.trim());
          setPage(0);
        }}
      >
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="e.g. Tableau, Stripe, Data Analyst"
          className="w-full sm:w-72"
          aria-label="Search jobs"
        />
        <Select label="Seniority" value={seniority} options={SENIORITY} onChange={(v) => (setSeniority(v), setPage(0))} />
        <Select label="Work mode" value={workMode} options={WORK_MODES} onChange={(v) => (setWorkMode(v), setPage(0))} />
        <Button type="submit">Search</Button>
      </form>

      {error ? (
        <ErrorMessage message={error} />
      ) : !data ? (
        <Loading slow={slow} height="h-96" />
      ) : (
        <Card>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">{data.total.toLocaleString()} jobs</p>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Level</TableHead>
                    <TableHead>Skills</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.jobs.map((job) => (
                    <TableRow key={job.job_id}>
                      <TableCell className="max-w-64 whitespace-normal font-medium">{job.title}</TableCell>
                      <TableCell>{job.company}</TableCell>
                      <TableCell className="max-w-48 whitespace-normal text-muted-foreground">{job.location}</TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span>{job.seniority}</span>
                          {job.work_mode !== "Unknown" && (
                            <span className="text-xs text-muted-foreground">{job.work_mode}</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-72">
                        <div className="flex flex-wrap gap-1">
                          {job.skills.slice(0, 5).map((s) => (
                            <Badge key={s} variant="secondary">{s}</Badge>
                          ))}
                          {job.skills.length > 5 && <Badge variant="outline">+{job.skills.length - 5}</Badge>}
                        </div>
                      </TableCell>
                      <TableCell>
                        {job.url && (
                          <a href={job.url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">
                            Apply
                          </a>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="flex items-center justify-between">
              <Button variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1} of {pages}
              </span>
              <Button variant="outline" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border bg-background px-3 text-sm"
    >
      <option value="">{label}: all</option>
      {options.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  );
}
