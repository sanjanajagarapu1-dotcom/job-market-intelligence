"""
fetch_jobs.py - Step 1 of our pipeline.
Gets job postings from the Adzuna API and saves them to a CSV file.
"""

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

# ---- 1. Load secret keys from the .env file ----
load_dotenv()
# .strip() removes accidental spaces/line breaks from copy-pasted keys
APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()

# ---- 2. Settings: what to search for ----
SEARCH_TERMS = ["data analyst", "data scientist"]
PAGES_PER_TERM = 2          # each page = up to 50 jobs
RESULTS_PER_PAGE = 50
BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"


def fetch_page(search_term, page):
    """Ask Adzuna for one page of jobs and return them as a list."""
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "what": search_term,
        "results_per_page": RESULTS_PER_PAGE,
        "content-type": "application/json",
    }
    response = requests.get(BASE_URL.format(page=page), params=params, timeout=30)
    response.raise_for_status()  # stop with an error if the request failed
    return response.json().get("results", [])


def clean_job(raw, search_term):
    """Keep only the fields we need, in a simple flat format."""
    return {
        "job_id": raw.get("id"),
        "source": "adzuna",
        "title": raw.get("title"),
        "company": raw.get("company", {}).get("display_name"),
        "location": raw.get("location", {}).get("display_name"),
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "contract_time": raw.get("contract_time"),
        "category": raw.get("category", {}).get("label"),
        "description": raw.get("description"),
        "url": raw.get("redirect_url"),
        "posted_date": raw.get("created"),
        "search_term": search_term,
    }


def main():
    # Safety check: are the keys loaded?
    if not APP_ID or not APP_KEY:
        print("ERROR: Adzuna keys not found. Check your .env file.")
        return

    all_jobs = []
    for term in SEARCH_TERMS:
        for page in range(1, PAGES_PER_TERM + 1):
            print(f"Fetching '{term}' - page {page} ...")
            results = fetch_page(term, page)
            all_jobs.extend(clean_job(job, term) for job in results)
            time.sleep(2)  # be polite: wait 2 seconds between calls

    # Turn the list into a table and remove duplicate jobs
    df = pd.DataFrame(all_jobs).drop_duplicates(subset="job_id")

    os.makedirs("data", exist_ok=True)
    df.to_csv("data/jobs.csv", index=False)
    print(f"\nDone! Saved {len(df)} jobs to data/jobs.csv")


if __name__ == "__main__":
    main()
