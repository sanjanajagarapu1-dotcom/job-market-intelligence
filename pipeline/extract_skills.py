r"""
extract_skills.py - Step 2 of our pipeline.
Reads the job CSVs, asks the Groq AI to pull structured info out of each
job description, and saves the result to data/jobs_enriched.csv.
Jobs that were already processed are skipped, so re-running is cheap.

Usage:
    python pipeline\extract_skills.py        # process all new jobs
    python pipeline\extract_skills.py 5      # test on 5 new jobs only
"""

import json
import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv
from groq import Groq, RateLimitError
from supabase import create_client

# ---- 1. Setup ----
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY", "").strip())

# The free tier allows ~8,000 tokens per minute PER MODEL, so we take turns
# between two similar models to double our speed.
MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
INPUT_FILES = ["data/company_jobs.csv", "data/jobs.csv"]  # full descriptions first
OUTPUT_FILE = "data/jobs_enriched.csv"
MAX_DESCRIPTION_CHARS = 3000  # long posts are trimmed to save AI tokens
SAVE_EVERY = 10               # save progress every 10 jobs

# Words that usually start the part of a posting that lists skills
REQUIREMENT_MARKERS = [
    "qualifications", "requirements", "what you'll need", "what you will need",
    "you have", "you'll bring", "about you", "skills", "experience with",
]

# ---- 2. Instructions for the AI ----
SYSTEM_PROMPT = """You extract structured data from job postings.
Return ONLY a JSON object with exactly these keys:
- "skills": list of technical skills and tools mentioned (e.g. "SQL", "Python",
  "Tableau", "Power BI", "Excel", "AWS", "Machine Learning"). Use standard
  capitalization. Max 15. Do not include soft skills.
- "seniority": one of "Intern", "Entry", "Mid", "Senior", "Lead", "Unknown"
- "work_mode": one of "Remote", "Hybrid", "Onsite", "Unknown"
- "years_experience": minimum years of experience required as an integer, or null
Only use information present in the posting. If unsure, use "Unknown" or null."""


def requirements_part(description):
    """Keep the part of the description most likely to list skills.
    Postings usually start with 'About us' text and list skills later on."""
    text = str(description)
    lower = text.lower()
    positions = [lower.find(m) for m in REQUIREMENT_MARKERS if lower.find(m) > 0]
    start = min(positions) if positions else 0
    return text[start:start + MAX_DESCRIPTION_CHARS]


def extract(title, description, model):
    """Send one job to the AI and return the extracted data as a dict."""
    for attempt in range(3):  # retry up to 3 times if we hit the rate limit
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Title: {title}\n\nDescription: {description}"},
                ],
                response_format={"type": "json_object"},  # force valid JSON
                reasoning_effort="low",                   # faster, fewer tokens
                temperature=0,
            )
            return json.loads(response.choices[0].message.content)
        except RateLimitError:
            wait = 30 * (attempt + 1)
            print(f"  Rate limit hit - waiting {wait}s ...")
            time.sleep(wait)
    return {}


def load_done_from_db():
    """No local results file (e.g. on GitHub Actions)? Get the jobs the AI
    already processed from Supabase, so we don't process them again."""
    supabase = create_client(os.getenv("SUPABASE_URL", "").strip(), os.getenv("SUPABASE_KEY", "").strip())
    rows, start = [], 0
    while True:  # Supabase returns max 1000 rows per request
        batch = (supabase.table("jobs").select("job_id, skills, seniority, work_mode, years_experience")
                 .not_.is_("seniority", "null").range(start, start + 999).execute().data)
        rows.extend(batch)
        if len(batch) < 1000:
            break
        start += 1000
    done = pd.DataFrame(rows, columns=["job_id", "skills", "seniority", "work_mode", "years_experience"])
    done["skills"] = done["skills"].apply(lambda s: "; ".join(s) if isinstance(s, list) else "")
    return done


def main():
    jobs = pd.concat([pd.read_csv(f) for f in INPUT_FILES if os.path.exists(f)])

    # Skip jobs we already processed in an earlier run
    done = pd.read_csv(OUTPUT_FILE) if os.path.exists(OUTPUT_FILE) else load_done_from_db()
    done["job_id"] = done["job_id"].astype(str)
    jobs["job_id"] = jobs["job_id"].astype(str)
    todo = jobs[~jobs["job_id"].isin(done["job_id"])]

    # Optional: only process N jobs (for quick testing)
    if len(sys.argv) > 1:
        todo = todo.head(int(sys.argv[1]))
    print(f"{len(todo)} new jobs to process ({len(done)} already done)\n")

    results = []

    def save():
        combined = pd.concat([done, pd.DataFrame(results)], ignore_index=True)
        combined.to_csv(OUTPUT_FILE, index=False)
        return len(combined)

    try:
        for i, row in enumerate(todo.itertuples(), start=1):
            model = MODELS[i % len(MODELS)]  # take turns between models
            print(f"[{i}/{len(todo)}] {row.title} - {row.company}")
            try:
                data = extract(row.title, requirements_part(row.description), model)
            except Exception as e:  # one bad job shouldn't stop the whole run
                print(f"  Skipped: {e}")
                continue

            results.append({
                "job_id": row.job_id,
                "skills": "; ".join(data.get("skills") or []),
                "seniority": data.get("seniority", "Unknown"),
                "work_mode": data.get("work_mode", "Unknown"),
                "years_experience": data.get("years_experience"),
            })
            if i % SAVE_EVERY == 0:
                save()
    finally:
        # Save progress even if you stop the script early with Ctrl + C
        total = save()
        print(f"\nSaved {len(results)} new results ({total} total) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
