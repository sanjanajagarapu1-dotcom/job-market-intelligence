"use client";

import { useState } from "react";

import { HorizontalBars } from "@/components/charts";
import { ErrorMessage, Loading } from "@/components/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ResumeResult, fetchJson } from "@/lib/api";

export default function ResumePage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ResumeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);

  async function analyze() {
    if (!file) return;
    setBusy(true);
    setSlow(false);
    setError(null);
    setResult(null);
    const timer = setTimeout(() => setSlow(true), 4000); // free server may be asleep
    const form = new FormData();
    form.append("file", file);
    try {
      setResult(await fetchJson<ResumeResult>("/resume/match?limit=15", { method: "POST", body: form }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      clearTimeout(timer);
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Resume Analyzer</h1>
        <p className="mt-1 text-muted-foreground">
          Upload your resume to find your best-matching jobs and the skills worth learning next. Your resume is
          analyzed in memory and never stored.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-4">
          <input
            type="file"
            accept="application/pdf,.pdf"
            aria-label="Resume PDF"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:text-sm"
          />
          <Button onClick={analyze} disabled={!file || busy}>
            {busy ? "Analyzing…" : "Analyze resume"}
          </Button>
        </CardContent>
      </Card>

      {busy && <Loading slow={slow} height="h-40" />}
      {error && <ErrorMessage message={error} />}

      {result && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Skills found in your resume ({result.skills_found.length})</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {result.skills_found.length ? (
                result.skills_found.map((s) => <Badge key={s} variant="secondary">{s}</Badge>)
              ) : (
                <p className="text-sm text-muted-foreground">No known skills found.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Best-matching jobs</CardTitle>
              <CardDescription>
                Match = 50% skill overlap + 50% meaning similarity (AI embeddings + pgvector).
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Match</TableHead>
                    <TableHead>Job</TableHead>
                    <TableHead>Skills you&apos;re missing</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.matches.map((m) => (
                    <TableRow key={m.job_id}>
                      <TableCell className="w-40">
                        <MatchBar value={m.match} />
                        <p className="mt-1 text-xs text-muted-foreground">
                          Skills {Math.round(m.skill_match)}% · Meaning {Math.round(m.meaning_match)}%
                        </p>
                      </TableCell>
                      <TableCell className="max-w-72 whitespace-normal">
                        <p className="font-medium">{m.title}</p>
                        <p className="text-sm text-muted-foreground">
                          {m.company} · {m.location}
                        </p>
                      </TableCell>
                      <TableCell className="max-w-72">
                        <div className="flex flex-wrap gap-1">
                          {m.missing_skills.length ? (
                            m.missing_skills.map((s) => <Badge key={s} variant="outline">{s}</Badge>)
                          ) : (
                            <span className="text-sm text-muted-foreground">None 🎉</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {m.url && (
                          <a href={m.url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">
                            Apply
                          </a>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {result.skills_to_learn.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Top skills to learn next</CardTitle>
                <CardDescription>Skills most often required by these jobs that aren&apos;t in your resume.</CardDescription>
              </CardHeader>
              <CardContent>
                <HorizontalBars data={result.skills_to_learn} height={320} />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function MatchBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-muted">
        <div className="h-2 rounded-full bg-blue-600" style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-medium tabular-nums">{Math.round(value)}%</span>
    </div>
  );
}
