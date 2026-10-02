r"""
fetch_company_jobs.py - Step 1b of our pipeline.
Gets data jobs straight from company career pages using the official public
Greenhouse and Lever job board APIs (free, no key needed). Unlike Adzuna,
these include the FULL job description, so the AI can find skills.

Usage:
    python pipeline\fetch_company_jobs.py
"""

import html
import os
import re
import time
from datetime import datetime, timezone

import pandas as pd
import requests

COMPANIES_FILE = "pipeline/companies.csv"
OUTPUT_FILE = "data/company_jobs.csv"

# Only keep jobs whose title contains one of these words
TITLE_KEYWORDS = [
    "data analyst", "data scientist", "data science", "analytics",
    "business intelligence", "bi analyst", "business analyst",
    "data engineer", "machine learning",
]


def strip_html(text):
    """Turn HTML like '<p>Know <b>SQL</b></p>' into plain text 'Know SQL'."""
    text = html.unescape(text or "")          # &lt;p&gt; -> <p>
    text = re.sub(r"<[^>]+>", " ", text)      # remove tags
    return re.sub(r"\s+", " ", text).strip()  # collapse extra spaces


def is_data_job(title):
    return any(word in title.lower() for word in TITLE_KEYWORDS)


def fetch_greenhouse(slug, company):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    jobs = requests.get(url, timeout=30).json().get("jobs", [])
    return [
        {
            "job_id": f"gh-{job['id']}",
            "source": "greenhouse",
            "title": job["title"],
            "company": company,
            "location": (job.get("location") or {}).get("name"),
            "description": strip_html(job.get("content")),
            "url": job.get("absolute_url"),
            "posted_date": job.get("first_published") or job.get("updated_at"),
        }
        for job in jobs if is_data_job(job["title"])
    ]


def fetch_lever(slug, company):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    jobs = requests.get(url, timeout=30).json()
    results = []
    for job in jobs:
        if not is_data_job(job["text"]):
            continue
        # Lever splits the description into a main part plus bullet lists
        parts = [job.get("descriptionPlain", "")]
        parts += [f"{lst['text']}: {strip_html(lst['content'])}" for lst in job.get("lists", [])]
        results.append({
            "job_id": f"lever-{job['id']}",
            "source": "lever",
            "title": job["text"],
            "company": company,
            "location": job.get("categories", {}).get("location"),
            "contract_time": job.get("categories", {}).get("commitment"),
            "description": " ".join(parts).strip(),
            "url": job.get("hostedUrl"),
            # Lever gives milliseconds since 1970 - convert to a date
            "posted_date": datetime.fromtimestamp(job["createdAt"] / 1000, tz=timezone.utc).isoformat(),
        })
    return results


def main():
    companies = pd.read_csv(COMPANIES_FILE)
    fetchers = {"greenhouse": fetch_greenhouse, "lever": fetch_lever}

    all_jobs = []
    for c in companies.itertuples():
        try:
            jobs = fetchers[c.platform](c.slug, c.company)
            print(f"{c.company:<15} {len(jobs):>3} data jobs")
            all_jobs.extend(jobs)
        except Exception as e:  # one broken board shouldn't stop the run
            print(f"{c.company:<15} skipped ({e})")
        time.sleep(1)  # be polite

    df = pd.DataFrame(all_jobs).drop_duplicates(subset="job_id")
    os.makedirs("data", exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nDone! Saved {len(df)} company jobs to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
