r"""
load_to_db.py - Step 3 of our pipeline.
Uploads jobs from data/jobs.csv and data/company_jobs.csv (plus any AI
results from data/jobs_enriched.csv) into the Supabase "jobs" table.

Usage:
    python pipeline\load_to_db.py
"""

import math
import os

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# ---- 1. Connect to Supabase ----
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

JOBS_FILES = ["data/jobs.csv", "data/company_jobs.csv"]
ENRICHED_FILE = "data/jobs_enriched.csv"
AI_COLUMNS = ["skills", "seniority", "work_mode", "years_experience"]
BATCH_SIZE = 100  # upload 100 rows at a time


def clean_value(value):
    """Databases don't understand pandas 'NaN' (empty) - turn it into None."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def to_row(job):
    """Convert one CSV row into the format our database table expects."""
    row = {key: clean_value(value) for key, value in job.items()}
    row["job_id"] = str(row["job_id"])
    row["source"] = row.get("source") or "adzuna"
    # "SQL; Python; Tableau" -> ["SQL", "Python", "Tableau"]
    row["skills"] = [s.strip() for s in row["skills"].split(";")] if row.get("skills") else None
    if row.get("years_experience") is not None:
        row["years_experience"] = int(row["years_experience"])
    return row


def main():
    jobs = pd.concat([pd.read_csv(f) for f in JOBS_FILES if os.path.exists(f)])
    jobs["job_id"] = jobs["job_id"].astype(str)

    # If the AI step has run, attach its results to the matching jobs
    if os.path.exists(ENRICHED_FILE):
        enriched = pd.read_csv(ENRICHED_FILE)[["job_id"] + AI_COLUMNS]
        enriched["job_id"] = enriched["job_id"].astype(str)
        jobs = jobs.merge(enriched, on="job_id", how="left")

    rows = [to_row(job) for job in jobs.to_dict(orient="records")]

    # "upsert" = insert new jobs, update ones that already exist (no duplicates)
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        supabase.table("jobs").upsert(batch, on_conflict="job_id").execute()
        print(f"Uploaded rows {start + 1} - {start + len(batch)}")

    total = supabase.table("jobs").select("job_id", count="exact").limit(1).execute().count
    print(f"\nDone! The database now has {total} jobs.")


if __name__ == "__main__":
    main()
