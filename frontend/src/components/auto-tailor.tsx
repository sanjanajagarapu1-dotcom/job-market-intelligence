"use client";

import JSZip from "jszip";
import { useEffect, useRef, useState } from "react";

import { ActionButtons, TailoredView, jobSlug, tailoredToText } from "@/components/ai-panels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type CoverLetter, type Match, type TailoredResume, postJson } from "@/lib/api";

type Status = "waiting" | "working" | "done" | "error";
type Item = { job: Match; status: Status; tailored?: TailoredResume; letter?: CoverLetter; error?: string };

const RETRIES = 3;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Retry a request when the free AI tier is busy (rate limited) or the server is waking up. */
async function withRetry<T>(request: () => Promise<T>, isCancelled: () => boolean): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await request();
    } catch (e) {
      if (attempt >= RETRIES || isCancelled()) throw e;
      await sleep(15000 * attempt);
    }
  }
}

/**
 * Automatically creates a tailored resume + cover letter for each of the given jobs,
 * one job at a time (to stay within the free AI rate limit).
 */
export function AutoTailor({ jobs, resumeText }: { jobs: Match[]; resumeText: string }) {
  const [items, setItems] = useState<Item[]>(() => jobs.map((job) => ({ job, status: "waiting" })));
  const [running, setRunning] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const stopRequested = useRef(false); // set by the Stop button

  useEffect(() => {
    let unmounted = false; // each run of this effect gets its own flag
    const stop = () => unmounted || stopRequested.current;
    const update = (i: number, patch: Partial<Item>) =>
      !unmounted && setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));

    (async () => {
      await sleep(100); // lets React's double-mount in development cancel the first run before any request
      for (let i = 0; i < jobs.length; i++) {
        if (stop()) break;
        update(i, { status: "working" });
        const body = { resume_text: resumeText, job_id: jobs[i].job_id };
        try {
          const tailored = await withRetry(() => postJson<TailoredResume>("/resume/tailor", body), stop);
          update(i, { tailored });
          const letter = await withRetry(() => postJson<CoverLetter>("/resume/cover-letter", body), stop);
          update(i, { letter, status: "done" });
        } catch (e) {
          update(i, { status: "error", error: (e as Error).message });
        }
      }
      if (!unmounted) setRunning(false);
    })();

    return () => {
      unmounted = true;
    };
  }, [jobs, resumeText]);

  const done = items.filter((it) => it.status === "done").length;
  const finished = items.filter((it) => it.status === "done" || it.status === "error").length;

  async function downloadAll() {
    const zip = new JSZip();
    const index = ["Tailored applications", "======================", ""];
    items.forEach((it, n) => {
      if (!it.tailored && !it.letter) return;
      const folder = zip.folder(`${String(n + 1).padStart(2, "0")}-${jobSlug(it.job)}`)!;
      if (it.tailored) folder.file("tailored_resume.txt", tailoredToText(it.tailored));
      if (it.letter) folder.file("cover_letter.txt", it.letter.cover_letter);
      index.push(`${n + 1}. ${it.job.title} - ${it.job.company} (match ${Math.round(it.job.match)}%)`, `   Apply: ${it.job.url ?? "n/a"}`, "");
    });
    index.push("AI-generated from your resume. Review and edit everything before sending.");
    zip.file("README.txt", index.join("\n"));
    const blob = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tailored-applications.zip";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card className="border-blue-200">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Automatic tailoring: top {jobs.length} jobs</CardTitle>
            <CardDescription>
              {running
                ? `Creating a tailored resume and cover letter for each job… ${finished} of ${jobs.length} done. This takes a few minutes on the free AI tier.`
                : `Finished: ${done} of ${jobs.length} ready.`}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {running && (
              <Button variant="outline" size="sm" onClick={() => (stopRequested.current = true)}>
                Stop
              </Button>
            )}
            <Button size="sm" onClick={downloadAll} disabled={done === 0}>
              Download all (ZIP)
            </Button>
          </div>
        </div>
        <div className="mt-3 h-2 rounded-full bg-muted">
          <div
            className="h-2 rounded-full bg-blue-600 transition-all"
            style={{ width: `${(finished / jobs.length) * 100}%` }}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          ✍️ AI-generated from your resume, using only facts from it. Always review and edit before sending.
        </p>
        {items.map((it) => (
          <div key={it.job.job_id} className="rounded-md border bg-background">
            <div className="flex flex-wrap items-center gap-3 p-3">
              <StatusBadge status={it.status} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{it.job.title}</p>
                <p className="text-sm text-muted-foreground">
                  {it.job.company} · match {Math.round(it.job.match)}%
                </p>
              </div>
              {it.status === "done" && (
                <Button size="sm" variant="outline" onClick={() => setOpen(open === it.job.job_id ? null : it.job.job_id)}>
                  {open === it.job.job_id ? "Hide" : "View"}
                </Button>
              )}
              {it.job.url && (
                <a href={it.job.url} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">
                  Apply ↗
                </a>
              )}
            </div>
            {it.status === "error" && <p className="px-3 pb-3 text-sm text-destructive">{it.error}</p>}
            {open === it.job.job_id && it.tailored && it.letter && (
              <div className="space-y-6 border-t p-4">
                <TailoredView data={it.tailored} />
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Cover letter</h3>
                  <ActionButtons text={it.letter.cover_letter} filename={`cover-letter-${jobSlug(it.job)}.txt`} />
                  <div className="whitespace-pre-wrap rounded-md border p-4 text-sm leading-relaxed">
                    {it.letter.cover_letter}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const label = { waiting: "Waiting", working: "Writing…", done: "Ready ✓", error: "Failed" }[status];
  const variant = status === "done" ? "default" : status === "error" ? "destructive" : "outline";
  return <Badge variant={variant} className="w-20 justify-center">{label}</Badge>;
}
