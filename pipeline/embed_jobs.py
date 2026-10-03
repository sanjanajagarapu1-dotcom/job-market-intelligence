r"""
embed_jobs.py - Step 4 of our pipeline.
Turns each job into an "embedding" (384 numbers that capture its meaning)
and saves it in Supabase, so resumes can be matched to jobs by meaning,
not just exact keywords. Only jobs without an embedding are processed.

Usage:
    python pipeline\embed_jobs.py
"""

import os

from dotenv import load_dotenv
from fastembed import TextEmbedding
from supabase import create_client

# ---- 1. Setup ----
load_dotenv()
# .strip() removes accidental spaces/line breaks from copy-pasted keys
supabase = create_client(os.getenv("SUPABASE_URL", "").strip(), os.getenv("SUPABASE_KEY", "").strip())

# A small, free model that runs on your own computer (downloads ~70 MB once)
MODEL_NAME = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 50
MAX_DESCRIPTION_CHARS = 1500


def job_to_text(job):
    """Combine the most meaningful parts of a job into one piece of text."""
    skills = ", ".join(job.get("skills") or [])
    description = (job.get("description") or "")[:MAX_DESCRIPTION_CHARS]
    return f"{job['title']}. Skills: {skills}. {description}"


def jobs_without_embedding():
    rows, start = [], 0
    while True:  # Supabase returns max 1000 rows per request
        batch = (supabase.table("jobs").select("job_id, title, skills, description")
                 .is_("embedding", "null").range(start, start + 999).execute().data)
        rows.extend(batch)
        if len(batch) < 1000:
            break
        start += 1000
    return rows


def main():
    jobs = jobs_without_embedding()
    print(f"{len(jobs)} jobs need an embedding")
    if not jobs:
        return

    model = TextEmbedding(MODEL_NAME)

    for start in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[start:start + BATCH_SIZE]
        vectors = model.passage_embed([job_to_text(job) for job in batch])
        rows = [{"job_id": job["job_id"], "embedding": vector.tolist()}
                for job, vector in zip(batch, vectors)]
        # upsert only touches the embedding column of existing jobs
        supabase.table("jobs").upsert(rows, on_conflict="job_id").execute()
        print(f"Embedded jobs {start + 1} - {start + len(batch)}")

    print("\nDone!")


if __name__ == "__main__":
    main()
