"""Tests for the FastAPI backend, using a fake jobs table instead of Supabase."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import data
from backend.main import app


@pytest.fixture
def client(fake_jobs, monkeypatch):
    # Replace database calls with the fake table and a fake "meaning" score
    monkeypatch.setattr(data, "get_jobs", lambda: fake_jobs)
    monkeypatch.setattr(data, "_semantic_similarity", lambda text: {"1": 100.0, "2": 40.0, "3": 0.0})
    return TestClient(app)


# ---------- logic in data.py ----------
def test_normalize_skills_merges_spelling_variants():
    df = pd.DataFrame({"skills": [["Power BI", "SQL"], ["power bi"], ["Power BI", "sql "]]})
    result = data._normalize_skills(df)
    assert result["skills"].tolist() == [["Power BI", "SQL"], ["Power BI"], ["Power BI", "SQL"]]


def test_filter_jobs_by_search_and_level(fake_jobs):
    assert data.filter_jobs(fake_jobs, search="tableau")["job_id"].tolist() == ["1"]  # matches a skill
    assert data.filter_jobs(fake_jobs, search="globex")["job_id"].tolist() == ["2", "3"]  # matches company
    assert data.filter_jobs(fake_jobs, seniority="Senior")["job_id"].tolist() == ["2"]


def test_summary(fake_jobs):
    s = data.summary(fake_jobs)
    assert s["jobs"] == 3
    assert s["companies"] == 2
    assert s["avg_min_salary"] == 70000
    assert s["remote_share"] == 0.5  # 1 remote out of 2 jobs with a known work mode


def test_top_skills(fake_jobs):
    assert data.top_skills(fake_jobs, 2) == [{"name": "SQL", "count": 2}, {"name": "Python", "count": 2}]


# ---------- API endpoints ----------
def test_health(client):
    assert client.get("/").json()["status"] == "ok"


def test_jobs_endpoint_filters_and_pages(client):
    body = client.get("/jobs", params={"search": "sql", "limit": 1}).json()
    assert body["total"] == 2
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["job_id"] == "2"  # newest first


def test_stats_endpoints(client):
    assert client.get("/stats/summary").json()["jobs"] == 3
    assert client.get("/stats/companies").json()[0] == {"name": "Globex", "count": 2}
    assert {r["name"] for r in client.get("/stats/work-mode").json()} == {"Remote", "Hybrid", "Unknown"}


def test_resume_match_ranks_and_finds_gaps(client, monkeypatch):
    monkeypatch.setattr(data, "_semantic_similarity", lambda text: {"1": 100.0, "2": 40.0, "3": 0.0})
    result = data.match_resume("I know SQL, Tableau and Excel.", data.get_jobs(), limit=3)
    assert result["skills_found"] == ["Excel", "SQL", "Tableau"]
    top = result["matches"][0]
    assert top["job_id"] == "1" and top["match"] == 100  # all skills + closest meaning
    assert {"name": "Python", "count": 2} in result["skills_to_learn"]


def test_resume_endpoint_rejects_non_pdf(client):
    response = client.post("/resume/match", files={"file": ("resume.txt", b"hello", "text/plain")})
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
