"use client";

import { useEffect, useState } from "react";

// Address of our FastAPI backend. Set NEXT_PUBLIC_API_URL to override (e.g. http://localhost:8000).
export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "https://job-market-api-fezz.onrender.com"
).replace(/\/$/, "");

// ---------- Shapes of the data the API returns ----------
export type NameCount = { name: string; count: number };

export type Summary = {
  jobs: number;
  companies: number;
  avg_min_salary: number | null;
  remote_share: number | null;
};

export type Job = {
  job_id: string;
  source: string | null;
  title: string | null;
  company: string | null;
  location: string | null;
  salary_min: number | null;
  url: string | null;
  posted_date: string | null;
  skills: string[];
  seniority: string;
  work_mode: string;
};

export type JobList = { total: number; jobs: Job[] };

export type Match = {
  job_id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  url: string | null;
  match: number;
  skill_match: number;
  meaning_match: number;
  missing_skills: string[];
};

export type ResumeResult = {
  resume_text: string;
  skills_found: string[];
  matches: Match[];
  skills_to_learn: NameCount[];
};

type JobInfo = {
  job_title: string | null;
  company: string | null;
  limited_description: boolean;
};

export type TailoredResume = JobInfo & {
  headline: string;
  summary: string;
  skills_to_highlight: string[];
  bullets: { original: string; rewritten: string }[];
  keywords_to_include: string[];
  missing_skills: string[];
  gaps: string[];
};

export type CoverLetter = JobInfo & { cover_letter: string };

/** POST JSON to the API (used by the tailoring and cover letter features). */
export function postJson<T>(path: string, body: unknown): Promise<T> {
  return fetchJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ---------- Calling the API ----------
export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    // FastAPI sends errors as {"detail": "..."}
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

// After this long without an answer, we tell the user the free server is waking up
const SLOW_MS = 4000;

/** Load data from a GET endpoint. Re-runs whenever `path` changes. */
export function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => !cancelled && setSlow(true), SLOW_MS);
    fetchJson<T>(path)
      .then((d) => !cancelled && (setData(d), setError(null)))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => {
        clearTimeout(timer);
        if (!cancelled) setSlow(false);
      });
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [path]);

  return { data, error, slow, loading: data === null && error === null };
}
