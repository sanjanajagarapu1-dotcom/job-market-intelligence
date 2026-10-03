-- Database setup for the Job Market Intelligence project (Supabase / PostgreSQL).
-- Run this once in the Supabase SQL Editor.

-- ---------- Jobs table ----------
create table if not exists jobs (
  job_id            text primary key,        -- unique ID, prevents duplicates
  source            text,                    -- adzuna, greenhouse or lever
  title             text,
  company           text,
  location          text,
  salary_min        numeric,
  salary_max        numeric,
  contract_time     text,
  category          text,
  description       text,
  url               text,
  posted_date       timestamptz,
  search_term       text,
  -- filled in by the AI (pipeline/extract_skills.py):
  skills            text[],
  seniority         text,
  work_mode         text,
  years_experience  int,
  fetched_at        timestamptz default now()
);

-- Block public access; the pipeline and app use the secret key.
alter table jobs enable row level security;

-- ---------- Semantic search with pgvector ----------
create extension if not exists vector with schema extensions;

-- 384-number embedding per job (pipeline/embed_jobs.py)
alter table jobs add column if not exists embedding vector(384);

-- Approximate-nearest-neighbour index for fast top-k searches as the table grows
create index if not exists jobs_embedding_idx
  on jobs using hnsw (embedding vector_cosine_ops);

-- Similarity of every job to a query embedding (e.g. a resume).
-- Ordering by the computed score forces an exact scan, so every job gets a score
-- (the HNSW index would only return an approximate top ~40).
create or replace function match_jobs(query_embedding vector(384), match_count int default 50)
returns table (job_id text, similarity float)
language sql stable
as $$
  select job_id, 1 - (embedding <=> query_embedding) as similarity
  from jobs
  where embedding is not null
  order by similarity desc
  limit match_count;
$$;
