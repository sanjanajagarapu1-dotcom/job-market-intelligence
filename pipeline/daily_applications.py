r"""
daily_applications.py - Automatic daily resume + cover letter tailoring (runs on YOUR computer).

Every run it:
  1. Reads your resume from private\resume.pdf (the "private" folder is never uploaded to GitHub)
  2. Finds jobs posted in the last few days that match you well and that it hasn't done before
  3. Writes a tailored resume and a cover letter for the top matches into
     private\applications\<date>\<number>-<company>-<job>\

Usage (from the project folder, with the venv active):
    python pipeline\daily_applications.py
    python pipeline\daily_applications.py --top 5 --min-match 70 --days 3
"""

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import ai, data  # noqa: E402  (needs ROOT on the path first)

PRIVATE = ROOT / "private"
RESUME = PRIVATE / "resume.pdf"
OUTPUT = PRIVATE / "applications"
PROCESSED_FILE = OUTPUT / "processed.json"  # job_ids already tailored, so we never repeat one
PAUSE_SECONDS = 10                          # be gentle with the free AI rate limit


def read_resume():
    if not RESUME.exists():
        sys.exit(f"Put your resume at {RESUME} and run again.")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(RESUME).pages)
    if len(text.strip()) < 50:
        sys.exit("Could not read text from your resume PDF (is it a scanned image?).")
    return text


def load_processed():
    return set(json.loads(PROCESSED_FILE.read_text())) if PROCESSED_FILE.exists() else set()


def save_processed(job_ids):
    PROCESSED_FILE.write_text(json.dumps(sorted(job_ids), indent=2))


def slug(job):
    s = re.sub(r"[^a-z0-9]+", "-", f"{job.get('company', '')}-{job.get('title', '')}".lower()).strip("-")
    return s[:70] or "job"


def tailored_to_text(t):
    lines = [t["headline"], "", "SUMMARY", t["summary"], "", "SKILLS", ", ".join(t["skills_to_highlight"]),
             "", "EXPERIENCE BULLETS", *[f"- {b['rewritten']}" for b in t["bullets"]], "",
             "--- Notes for you (not for the resume) ---",
             "Your original bullets:", *[f"  - {b['original']}" for b in t["bullets"]],
             f"Job keywords you already have: {', '.join(t['keywords_to_include']) or 'none'}",
             f"Job skills you don't show: {', '.join(t['missing_skills']) or 'none'}",
             *[f"Gap: {g}" for g in t["gaps"]]]
    return "\n".join(lines)


def with_retry(fn, *args):
    """Try up to 3 times, waiting longer each time (the free AI tier is sometimes busy)."""
    for attempt in range(1, 4):
        try:
            return fn(*args)
        except ai.AIUnavailable:
            if attempt == 3:
                raise
            time.sleep(30 * attempt)


def main():
    parser = argparse.ArgumentParser(description="Tailor your resume + cover letter for new matching jobs.")
    parser.add_argument("--top", type=int, default=10, help="max jobs per run (default 10)")
    parser.add_argument("--min-match", type=float, default=60, help="minimum match %% (default 60)")
    parser.add_argument("--days", type=int, default=7, help="only jobs posted in the last N days (default 7)")
    args = parser.parse_args()

    resume_text = read_resume()
    processed = load_processed()

    # Recent jobs we haven't tailored for yet
    jobs = data.get_jobs()
    posted = pd.to_datetime(jobs["posted_date"], errors="coerce", utc=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    candidates = jobs[(posted >= cutoff) & ~jobs["job_id"].isin(processed)]
    print(f"{len(candidates)} new jobs from the last {args.days} days")

    # Ask for extra matches, then keep one per company + title (the same job is often posted per city)
    matches, seen = [], set()
    for m in data.match_resume(resume_text, candidates, limit=args.top * 4)["matches"]:
        key = (str(m["company"]).lower(), str(m["title"]).lower())
        if m["match"] >= args.min_match and key not in seen:
            seen.add(key)
            matches.append(m)
    matches = matches[:args.top]
    if not matches:
        print(f"No new jobs with a match of {args.min_match:.0f}% or more today.")
        return
    print(f"Tailoring for {len(matches)} jobs...\n")

    day_dir = OUTPUT / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    start_number = len([p for p in day_dir.iterdir() if p.is_dir()])  # keep numbering if run twice a day
    index_lines = []

    for n, match in enumerate(matches, start=start_number + 1):
        job = data.get_job_detail(match["job_id"])
        if not job:
            continue
        print(f"[{n}] {job['title']} - {job['company']} (match {match['match']:.0f}%)")
        try:
            tailored = with_retry(ai.tailor_resume, resume_text, job)
            time.sleep(PAUSE_SECONDS)
            letter = with_retry(ai.write_cover_letter, resume_text, job)
            time.sleep(PAUSE_SECONDS)
        except ai.AIUnavailable as e:
            print(f"    skipped: {e}")
            continue

        folder = day_dir / f"{n:02d}-{slug(job)}"
        folder.mkdir(exist_ok=True)
        (folder / "tailored_resume.txt").write_text(tailored_to_text(tailored), encoding="utf-8")
        (folder / "cover_letter.txt").write_text(letter["cover_letter"], encoding="utf-8")
        index_lines += [f"{n}. {job['title']} - {job['company']} | match {match['match']:.0f}% | {job.get('location')}",
                        f"   Apply: {match.get('url')}", f"   Folder: {folder.name}", ""]
        processed.add(match["job_id"])
        save_processed(processed)  # save after every job, so a crash never loses work

    if index_lines:
        with open(day_dir / "README.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(index_lines) + "\n")
    print(f"\nDone! Files are in {day_dir}")
    print("Review and edit everything before sending: it's AI-generated from your resume.")


if __name__ == "__main__":
    main()
