r"""
main.py - The FastAPI backend: web addresses (endpoints) that return job data as JSON.

Run locally (from the project folder):
    uvicorn backend.main:app --reload
Then open http://localhost:8000/docs to try every endpoint in your browser.
"""

import io
import os
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader

from backend import data

app = FastAPI(
    title="Job Market Intelligence API",
    description="Data analyst & data scientist jobs with AI-extracted skills, market stats, and resume matching.",
    version="1.0.0",
)

# CORS: lets a website on another address (our future Next.js frontend) call this API.
# Set ALLOWED_ORIGINS="https://your-site.vercel.app" in production; "*" allows any site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------- Response shapes (these also document the API at /docs) ----------
class Job(BaseModel):
    job_id: str
    source: Optional[str]
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    salary_min: Optional[float]
    salary_max: Optional[float]
    url: Optional[str]
    posted_date: Optional[str]
    skills: list[str]
    seniority: str
    work_mode: str
    years_experience: Optional[int]


class JobList(BaseModel):
    total: int
    jobs: list[Job]


class Summary(BaseModel):
    jobs: int
    companies: int
    avg_min_salary: Optional[int]
    remote_share: Optional[float]


class NameCount(BaseModel):
    name: str
    count: int


class Match(BaseModel):
    job_id: str
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    url: Optional[str]
    match: float
    skill_match: float
    meaning_match: float
    missing_skills: list[str]


class ResumeResult(BaseModel):
    skills_found: list[str]
    matches: list[Match]
    skills_to_learn: list[NameCount]


# ---------- Filters shared by several endpoints ----------
def filtered_jobs(search=None, source=None, seniority=None, work_mode=None):
    return data.filter_jobs(data.get_jobs(), search, source, seniority, work_mode)


SEARCH = Query(None, description="Text to find in title, company or skills, e.g. 'tableau'")
SOURCE = Query(None, description="adzuna, greenhouse or lever")
SENIORITY = Query(None, description="Intern, Entry, Mid, Senior, Lead or Unknown")
WORK_MODE = Query(None, description="Remote, Hybrid, Onsite or Unknown")


# ---------- Endpoints ----------
@app.get("/", tags=["health"])
def health():
    """Quick check that the API is running."""
    return {"status": "ok", "docs": "/docs"}


@app.get("/jobs", response_model=JobList, tags=["jobs"])
def list_jobs(search: Optional[str] = SEARCH, source: Optional[str] = SOURCE,
              seniority: Optional[str] = SENIORITY, work_mode: Optional[str] = WORK_MODE,
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Search and filter jobs, newest first. Use limit/offset to page through results."""
    df = filtered_jobs(search, source, seniority, work_mode).sort_values("posted_date", ascending=False)
    return {"total": len(df), "jobs": data.to_records(df.iloc[offset:offset + limit])}


@app.get("/stats/summary", response_model=Summary, tags=["stats"])
def stats_summary(search: Optional[str] = SEARCH, source: Optional[str] = SOURCE,
                  seniority: Optional[str] = SENIORITY, work_mode: Optional[str] = WORK_MODE):
    """Headline numbers: job count, companies, average minimum salary, share of remote jobs."""
    return data.summary(filtered_jobs(search, source, seniority, work_mode))


@app.get("/stats/top-skills", response_model=list[NameCount], tags=["stats"])
def stats_top_skills(limit: int = Query(15, ge=1, le=100), source: Optional[str] = SOURCE,
                     seniority: Optional[str] = SENIORITY, work_mode: Optional[str] = WORK_MODE):
    """Most requested skills, by number of job postings."""
    return data.top_skills(filtered_jobs(None, source, seniority, work_mode), limit)


@app.get("/stats/companies", response_model=list[NameCount], tags=["stats"])
def stats_companies(limit: int = Query(15, ge=1, le=100), source: Optional[str] = SOURCE,
                    seniority: Optional[str] = SENIORITY, work_mode: Optional[str] = WORK_MODE):
    """Companies with the most job postings."""
    return data.count_values(filtered_jobs(None, source, seniority, work_mode)["company"], limit)


@app.get("/stats/seniority", response_model=list[NameCount], tags=["stats"])
def stats_seniority(source: Optional[str] = SOURCE, work_mode: Optional[str] = WORK_MODE):
    """Number of jobs at each seniority level."""
    return data.count_values(filtered_jobs(None, source, None, work_mode)["seniority"], 10)


@app.get("/stats/work-mode", response_model=list[NameCount], tags=["stats"])
def stats_work_mode(source: Optional[str] = SOURCE, seniority: Optional[str] = SENIORITY):
    """Number of jobs that are remote, hybrid, onsite or unknown."""
    return data.count_values(filtered_jobs(None, source, seniority, None)["work_mode"], 10)


@app.post("/resume/match", response_model=ResumeResult, tags=["resume"])
async def resume_match(file: UploadFile = File(..., description="Your resume as a PDF"),
                       limit: int = Query(15, ge=1, le=100)):
    """Upload a PDF resume: get the best-matching jobs (skills + meaning) and the top skills to learn."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(status_code=400, detail="PDF is too large (max 5 MB).")
    try:
        text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF.")
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text found in the PDF (is it a scanned image?).")
    return data.match_resume(text, data.get_jobs(), limit)
