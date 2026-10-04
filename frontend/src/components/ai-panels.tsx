"use client";

import { useEffect, useState } from "react";

import { ErrorMessage, Loading } from "@/components/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type CoverLetter, type Match, type TailoredResume, postJson } from "@/lib/api";

export type AiMode = "tailor" | "cover-letter";

/** Calls the tailoring or cover-letter endpoint for one job and shows the result. */
export function AiPanel({ job, mode, resumeText, onClose }: {
  job: Match;
  mode: AiMode;
  resumeText: string;
  onClose: () => void;
}) {
  const [tailored, setTailored] = useState<TailoredResume | null>(null);
  const [letter, setLetter] = useState<CoverLetter | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The parent gives this panel a new `key` per job + mode, so state always starts empty here
  useEffect(() => {
    let cancelled = false;
    const body = { resume_text: resumeText, job_id: job.job_id };
    const request = mode === "tailor"
      ? postJson<TailoredResume>("/resume/tailor", body).then((r) => !cancelled && setTailored(r))
      : postJson<CoverLetter>("/resume/cover-letter", body).then((r) => !cancelled && setLetter(r));
    request.catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [job.job_id, mode, resumeText]);

  const result = tailored ?? letter;
  const title = mode === "tailor" ? "Tailored resume" : "Cover letter";

  return (
    <Card id="ai-panel" className="border-blue-200">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle>
              {title}: {job.title}
            </CardTitle>
            <CardDescription>{job.company}</CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <ErrorMessage message={error} />}
        {!result && !error && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Writing with AI… this usually takes 5–20 seconds.</p>
            <Loading height="h-32" />
          </div>
        )}

        {result && (
          <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
            ✍️ AI-generated from your resume. It is instructed to use only facts from your resume, but always
            review and edit before sending.
            {result.limited_description &&
              " This job only has a short description, so the suggestions are more general."}
          </p>
        )}

        {tailored && <TailoredView data={tailored} />}
        {letter && (
          <>
            <ActionButtons text={letter.cover_letter} filename={fileName("cover-letter", job)} />
            <div className="whitespace-pre-wrap rounded-md border bg-background p-4 text-sm leading-relaxed">
              {letter.cover_letter}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function TailoredView({ data }: { data: TailoredResume }) {
  const asText = [
    data.headline,
    "",
    "SUMMARY",
    data.summary,
    "",
    "SKILLS",
    data.skills_to_highlight.join(", "),
    "",
    "EXPERIENCE BULLETS",
    ...data.bullets.map((b) => `- ${b.rewritten}`),
  ].join("\n");

  return (
    <div className="space-y-5">
      <ActionButtons text={asText} filename={fileName("tailored-resume", { title: data.job_title, company: data.company })} />

      <Section title="Headline"><p className="font-medium">{data.headline}</p></Section>
      <Section title="Summary"><p className="text-sm leading-relaxed">{data.summary}</p></Section>

      <Section title="Skills to put first">
        <Badges items={data.skills_to_highlight} variant="secondary" />
      </Section>

      <Section title="Rewritten bullet points" hint="Same facts as your original, worded for this job.">
        <ul className="space-y-3">
          {data.bullets.map((b, i) => (
            <li key={i} className="rounded-md border bg-background p-3 text-sm">
              <p className="font-medium">• {b.rewritten}</p>
              <p className="mt-1 text-xs text-muted-foreground">Original: {b.original}</p>
            </li>
          ))}
        </ul>
      </Section>

      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Job keywords you already have" hint="Make sure these words appear in your resume.">
          <Badges items={data.keywords_to_include} variant="secondary" empty="None found" />
        </Section>
        <Section title="Job skills you don't show" hint="Don't claim these. Learn them or mention related experience.">
          <Badges items={data.missing_skills} variant="outline" empty="None 🎉" />
        </Section>
      </div>

      {data.gaps.length > 0 && (
        <Section title="Other gaps to be aware of">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {data.gaps.map((g) => <li key={g}>{g}</li>)}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

function Badges({ items, variant, empty }: { items: string[]; variant: "secondary" | "outline"; empty?: string }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">{empty ?? "None"}</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((s) => <Badge key={s} variant={variant}>{s}</Badge>)}
    </div>
  );
}

function ActionButtons({ text, filename }: { text: string; filename: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="outline"
        onClick={async () => {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
      >
        {copied ? "Copied ✓" : "Copy"}
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          a.click();
          URL.revokeObjectURL(url);
        }}
      >
        Download .txt
      </Button>
    </div>
  );
}

function fileName(kind: string, job: { title?: string | null; company?: string | null }) {
  const slug = `${job.company ?? ""}-${job.title ?? ""}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${kind}-${slug || "job"}.txt`;
}
