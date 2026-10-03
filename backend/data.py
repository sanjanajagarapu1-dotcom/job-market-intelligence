"""
data.py - The logic behind the API: loading jobs from Supabase,
filtering them, computing stats, and matching a resume to jobs.
main.py only defines the web addresses (endpoints) and calls these functions.
"""

import os
import re
import time
from collections import Counter
from functools import lru_cache

import pandas as pd
from dotenv import load_dotenv
from fastembed import TextEmbedding
from supabase import create_client

load_dotenv()

CACHE_SECONDS = 600  # reload jobs from the database at most every 10 minutes
JOB_COLUMNS = ("job_id, source, title, company, location, salary_min, salary_max, url, "
               "posted_date, search_term, skills, seniority, work_mode, years_experience")

_cache = {"jobs": None, "loaded_at": 0.0}


@lru_cache  # connect once and re-use the connection
def get_supabase():
    # .strip() removes accidental spaces/line breaks from copy-pasted keys
    return create_client(os.getenv("SUPABASE_URL", "").strip(), os.getenv("SUPABASE_KEY", "").strip())


@lru_cache  # load the embedding model once (~70 MB)
def get_embedding_model():
    return TextEmbedding("BAAI/bge-small-en-v1.5")


# ---------- Loading ----------
def _fetch_all_jobs():
    rows, start = [], 0
    while True:  # Supabase returns max 1000 rows per request
        batch = get_supabase().table("jobs").select(JOB_COLUMNS).range(start, start + 999).execute().data
        rows.extend(batch)
        if len(batch) < 1000:
            break
        start += 1000

    df = pd.DataFrame(rows)
    df["skills"] = df["skills"].apply(lambda s: s if isinstance(s, list) else [])
    for col in ["seniority", "work_mode"]:
        df[col] = df[col].fillna("Unknown")
    return _normalize_skills(df)


def _normalize_skills(df):
    """Merge spelling variants like 'Power BI' / 'power bi' into one name."""
    counts = Counter(s.strip() for skills in df["skills"] for s in skills)
    display = {}
    for skill, _ in counts.most_common():  # most common spelling wins
        display.setdefault(skill.lower(), skill)
    df["skills"] = df["skills"].apply(lambda skills: sorted({display[s.strip().lower()] for s in skills}))
    return df


def get_jobs():
    """All jobs as a table, cached in memory for CACHE_SECONDS."""
    if _cache["jobs"] is None or time.time() - _cache["loaded_at"] > CACHE_SECONDS:
        _cache["jobs"] = _fetch_all_jobs()
        _cache["loaded_at"] = time.time()
    return _cache["jobs"]


# ---------- Filtering ----------
def filter_jobs(df, search=None, source=None, seniority=None, work_mode=None):
    if source:
        df = df[df["source"] == source]
    if seniority:
        df = df[df["seniority"] == seniority]
    if work_mode:
        df = df[df["work_mode"] == work_mode]
    if search:
        q = search.lower()
        df = df[
            df["title"].str.lower().str.contains(q, na=False, regex=False)
            | df["company"].str.lower().str.contains(q, na=False, regex=False)
            | df["skills"].apply(lambda skills: any(q in s.lower() for s in skills))
        ]
    return df


def to_records(df):
    """DataFrame -> list of dicts that can be sent as JSON (NaN -> None)."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


# ---------- Stats ----------
def summary(df):
    with_salary = df["salary_min"].dropna()
    known_mode = df[df["work_mode"] != "Unknown"]
    return {
        "jobs": len(df),
        "companies": int(df["company"].nunique()),
        "avg_min_salary": round(float(with_salary.mean())) if len(with_salary) else None,
        "remote_share": round(float((known_mode["work_mode"] == "Remote").mean()), 3) if len(known_mode) else None,
    }


def count_values(series, limit):
    counts = series.value_counts().head(limit)
    return [{"name": name, "count": int(n)} for name, n in counts.items()]


def top_skills(df, limit):
    return count_values(df.explode("skills").dropna(subset=["skills"])["skills"], limit)


# ---------- Resume matching ----------
def _semantic_similarity(resume_text):
    """{job_id: 0-100}: how close each job is to the resume in meaning (pgvector)."""
    vector = next(get_embedding_model().query_embed(resume_text)).tolist()
    rows = get_supabase().rpc("match_jobs", {"query_embedding": vector, "match_count": 5000}).execute().data
    if not rows:
        return {}
    sims = pd.Series({r["job_id"]: r["similarity"] for r in rows})
    # Raw similarities sit in a narrow band (e.g. 0.55-0.85), so spread them to 0-100
    return (100 * (sims - sims.min()) / (sims.max() - sims.min() or 1)).to_dict()


def match_resume(resume_text, df, limit=15):
    all_skills = {s for skills in get_jobs()["skills"] for s in skills}
    lower = resume_text.lower()
    my_skills = {s for s in all_skills
                 if re.search(rf"(?<![a-z0-9]){re.escape(s.lower())}(?![a-z0-9])", lower)}

    scored = df[df["skills"].str.len() > 0].copy()
    scored["matched"] = scored["skills"].apply(lambda skills: len(my_skills & set(skills)))
    scored["skill_match"] = (100 * scored["matched"] / scored["skills"].str.len()).round()
    scored["meaning_match"] = scored["job_id"].map(_semantic_similarity(resume_text)).fillna(0).round()
    scored["match"] = (0.5 * scored["skill_match"] + 0.5 * scored["meaning_match"]).round()
    scored["missing_skills"] = scored["skills"].apply(lambda skills: sorted(set(skills) - my_skills))
    top = scored.sort_values(["match", "matched"], ascending=False).head(limit)

    gaps = Counter(s for missing in scored["missing_skills"] for s in missing).most_common(10)
    return {
        "skills_found": sorted(my_skills),
        "matches": to_records(top[["job_id", "title", "company", "location", "url", "match",
                                   "skill_match", "meaning_match", "missing_skills"]]),
        "skills_to_learn": [{"name": s, "count": n} for s, n in gaps],
    }
