"""
Shared test setup. Tests never touch the real APIs or database:
we give the scripts fake keys and replace data loading with small fake tables.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent

# Fake keys so the scripts can be imported (their clients are created at import time)
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "sb_secret_test_key")
os.environ.setdefault("GROQ_API_KEY", "gsk_test_key")
os.environ.setdefault("ADZUNA_APP_ID", "test")
os.environ.setdefault("ADZUNA_APP_KEY", "test")

# Let tests import pipeline scripts (e.g. "import fetch_company_jobs") and the backend package
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def fake_jobs():
    """A tiny jobs table shaped like the real one in Supabase."""
    return pd.DataFrame([
        {"job_id": "1", "source": "adzuna", "title": "Data Analyst", "company": "Acme",
         "location": "Remote US", "salary_min": 70000.0, "salary_max": 90000.0, "url": "https://a/1",
         "posted_date": "2026-10-01T00:00:00+00:00", "search_term": "data analyst",
         "skills": ["SQL", "Tableau", "Excel"], "seniority": "Entry", "work_mode": "Remote",
         "years_experience": 1},
        {"job_id": "2", "source": "greenhouse", "title": "Senior Data Scientist", "company": "Globex",
         "location": "New York, NY", "salary_min": None, "salary_max": None, "url": "https://a/2",
         "posted_date": "2026-10-02T00:00:00+00:00", "search_term": None,
         "skills": ["Python", "SQL", "Machine Learning"], "seniority": "Senior", "work_mode": "Hybrid",
         "years_experience": 5},
        {"job_id": "3", "source": "lever", "title": "ML Engineer", "company": "Globex",
         "location": "Seattle, WA", "salary_min": None, "salary_max": None, "url": "https://a/3",
         "posted_date": "2026-09-30T00:00:00+00:00", "search_term": None,
         "skills": ["Python", "PyTorch"], "seniority": "Mid", "work_mode": "Unknown",
         "years_experience": None},
    ])
