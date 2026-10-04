"""Tests for the small helper functions in the data pipeline."""

import math

import extract_skills
import fetch_company_jobs
import load_to_db


# ---------- fetch_company_jobs ----------
def test_strip_html_removes_tags_and_entities():
    html = "&lt;p&gt;Know <b>SQL</b> &amp;   Python&lt;/p&gt;"
    assert fetch_company_jobs.strip_html(html) == "Know SQL & Python"


def test_strip_html_handles_empty():
    assert fetch_company_jobs.strip_html(None) == ""


def test_is_data_job_keeps_data_roles_only():
    assert fetch_company_jobs.is_data_job("Senior Data Analyst, Payments")
    assert fetch_company_jobs.is_data_job("Machine Learning Engineer")
    assert not fetch_company_jobs.is_data_job("Account Executive")
    assert not fetch_company_jobs.is_data_job("Software Engineer, Frontend")


# ---------- extract_skills ----------
def test_requirements_part_starts_at_qualifications():
    text = "About us: we sell shoes. " * 10 + "Qualifications: SQL, Python, Tableau."
    part = extract_skills.requirements_part(text)
    assert part.startswith("Qualifications")
    assert "SQL, Python, Tableau" in part


def test_requirements_part_falls_back_to_start_and_trims():
    text = "x" * 10_000
    part = extract_skills.requirements_part(text)
    assert part == "x" * extract_skills.MAX_DESCRIPTION_CHARS


# ---------- load_to_db ----------
def test_clean_value_turns_nan_into_none():
    assert load_to_db.clean_value(math.nan) is None
    assert load_to_db.clean_value(5) == 5
    assert load_to_db.clean_value("SQL") == "SQL"


def test_to_row_converts_csv_row_for_database():
    row = load_to_db.to_row({
        "job_id": 12345, "title": "Data Analyst", "skills": "SQL; Python ;Tableau",
        "years_experience": 3.0, "salary_min": math.nan,
    })
    assert row["job_id"] == "12345"                      # ids are stored as text
    assert row["source"] == "adzuna"                     # default source
    assert row["skills"] == ["SQL", "Python", "Tableau"]  # text -> list, trimmed
    assert row["years_experience"] == 3                  # float -> int
    assert row["salary_min"] is None                     # NaN -> None


def test_to_row_without_skills():
    row = load_to_db.to_row({"job_id": "gh-1", "source": "greenhouse", "skills": math.nan})
    assert row["skills"] is None
    assert row["source"] == "greenhouse"
