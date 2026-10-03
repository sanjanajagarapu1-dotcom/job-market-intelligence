r"""
app.py - The Streamlit dashboard.
Reads jobs from Supabase and shows market insights, a job explorer,
and a resume analyzer.

Run locally:
    streamlit run app.py
"""

import os
import re
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from fastembed import TextEmbedding
from pypdf import PdfReader
from supabase import create_client

st.set_page_config(page_title="Job Market Intelligence", page_icon="📊", layout="wide")


# ---------- 1. Load data ----------
def get_secret(name):
    """Read a key from .env locally, or from Streamlit secrets when deployed."""
    load_dotenv()
    if os.getenv(name):
        return os.getenv(name).strip()
    return st.secrets[name].strip()


@st.cache_resource  # connect once and re-use the connection
def get_supabase():
    return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))


@st.cache_resource  # load the embedding model once (~70 MB)
def get_embedding_model():
    return TextEmbedding("BAAI/bge-small-en-v1.5")


# Every column except the big "embedding" column, which the dashboard doesn't need
JOB_COLUMNS = ("job_id, source, title, company, location, salary_min, salary_max, url, "
               "posted_date, search_term, skills, seniority, work_mode, years_experience")


@st.cache_data(ttl=600)  # re-use the data for 10 minutes instead of reloading every click
def load_jobs():
    supabase = get_supabase()
    rows, start, page_size = [], 0, 1000
    while True:  # Supabase returns max 1000 rows per request, so we page through
        batch = supabase.table("jobs").select(JOB_COLUMNS).range(start, start + page_size - 1).execute().data
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    df = pd.DataFrame(rows)
    df["skills"] = df["skills"].apply(lambda s: s if isinstance(s, list) else [])
    df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce", utc=True)
    for col in ["seniority", "work_mode"]:
        df[col] = df[col].fillna("Unknown")
    return normalize_skills(df)


def normalize_skills(df):
    """Merge spelling variants like 'Power BI' / 'power bi' into one name."""
    counts = Counter(s.strip() for skills in df["skills"] for s in skills)
    display = {}
    for skill, _ in counts.most_common():  # most common spelling wins
        display.setdefault(skill.lower(), skill)
    df["skills"] = df["skills"].apply(lambda skills: sorted({display[s.strip().lower()] for s in skills}))
    return df


def semantic_similarity(resume_text):
    """Embed the resume and ask pgvector for its similarity to every job.
    Returns {job_id: score 0-100}, rescaled so the closest job = 100."""
    vector = next(get_embedding_model().query_embed(resume_text)).tolist()
    rows = get_supabase().rpc("match_jobs", {"query_embedding": vector, "match_count": 5000}).execute().data
    if not rows:
        return {}
    sims = pd.Series({r["job_id"]: r["similarity"] for r in rows})
    # Raw similarities sit in a narrow band (e.g. 0.55-0.85), so spread them to 0-100
    return (100 * (sims - sims.min()) / (sims.max() - sims.min() or 1)).to_dict()


jobs = load_jobs()

# ---------- 2. Sidebar filters ----------
st.sidebar.header("Filters")
sources = st.sidebar.multiselect("Source", sorted(jobs["source"].dropna().unique()))
seniority = st.sidebar.multiselect("Seniority", sorted(jobs["seniority"].unique()))
work_mode = st.sidebar.multiselect("Work mode", sorted(jobs["work_mode"].unique()))

filtered = jobs
if sources:
    filtered = filtered[filtered["source"].isin(sources)]
if seniority:
    filtered = filtered[filtered["seniority"].isin(seniority)]
if work_mode:
    filtered = filtered[filtered["work_mode"].isin(work_mode)]

st.title("📊 AI Job Market Intelligence")
st.caption("Data analyst & data scientist job postings, enriched with AI-extracted skills.")

overview_tab, explorer_tab, resume_tab = st.tabs(["Market Overview", "Job Explorer", "Resume Analyzer"])

# ---------- 3. Market overview ----------
with overview_tab:
    with_salary = filtered.dropna(subset=["salary_min"])
    known_mode = filtered[filtered["work_mode"] != "Unknown"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jobs", f"{len(filtered):,}")
    c2.metric("Companies", f"{filtered['company'].nunique():,}")
    c3.metric("Avg min salary", f"${with_salary['salary_min'].mean():,.0f}" if len(with_salary) else "n/a")
    c4.metric("Remote", f"{(known_mode['work_mode'] == 'Remote').mean():.0%}" if len(known_mode) else "n/a")

    left, right = st.columns(2)

    skill_counts = filtered.explode("skills").dropna(subset=["skills"])["skills"].value_counts().head(15)
    if len(skill_counts):
        fig = px.bar(skill_counts[::-1], orientation="h", title="Top 15 in-demand skills",
                     labels={"value": "Job postings", "index": ""})
        fig.update_layout(showlegend=False)
        left.plotly_chart(fig, width="stretch")
    else:
        left.info("No skills extracted yet - run pipeline/extract_skills.py")

    top_companies = filtered["company"].value_counts().head(15)
    fig = px.bar(top_companies[::-1], orientation="h", title="Companies hiring the most",
                 labels={"value": "Job postings", "index": ""})
    fig.update_layout(showlegend=False)
    right.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    order = ["Intern", "Entry", "Mid", "Senior", "Lead", "Unknown"]
    seniority_counts = filtered["seniority"].value_counts().reindex(order).dropna()
    left.plotly_chart(px.bar(seniority_counts, title="Jobs by seniority",
                             labels={"value": "Job postings", "index": ""}).update_layout(showlegend=False),
                      width="stretch")
    right.plotly_chart(px.pie(filtered, names="work_mode", title="Remote vs hybrid vs onsite", hole=0.4),
                       width="stretch")

    if len(with_salary):
        st.plotly_chart(px.box(with_salary, x="search_term", y="salary_min", points=False,
                               title="Minimum salary by role (Adzuna jobs)",
                               labels={"search_term": "", "salary_min": "Min salary ($)"}),
                        width="stretch")

# ---------- 4. Job explorer ----------
with explorer_tab:
    query = st.text_input("Search title, company or skill", placeholder="e.g. Tableau")
    results = filtered
    if query:
        q = query.lower()
        results = results[
            results["title"].str.lower().str.contains(q, na=False, regex=False)
            | results["company"].str.lower().str.contains(q, na=False, regex=False)
            | results["skills"].apply(lambda skills: any(q in s.lower() for s in skills))
        ]
    st.write(f"{len(results):,} jobs")
    st.dataframe(
        results[["title", "company", "location", "seniority", "work_mode", "skills", "salary_min", "url"]]
        .sort_values("title"),
        column_config={
            "url": st.column_config.LinkColumn("Apply", display_text="Open"),
            "salary_min": st.column_config.NumberColumn("Min salary", format="$%d"),
        },
        hide_index=True,
        width="stretch",
    )

# ---------- 5. Resume analyzer ----------
with resume_tab:
    st.write("Upload your resume to see which jobs fit you best and which skills to learn next.")
    uploaded = st.file_uploader("Resume (PDF)", type="pdf")

    if uploaded:
        resume_text = " ".join(page.extract_text() or "" for page in PdfReader(uploaded).pages)

        # Which known skills appear in the resume? (whole-word match)
        all_skills = {s for skills in jobs["skills"] for s in skills}
        my_skills = {s for s in all_skills
                     if re.search(rf"(?<![a-z0-9]){re.escape(s.lower())}(?![a-z0-9])", resume_text.lower())}

        st.subheader(f"Skills found in your resume ({len(my_skills)})")
        st.write(", ".join(sorted(my_skills)) or "No known skills found.")

        # Score 1 - skill match: what share of the job's skills do you have?
        scored = filtered[filtered["skills"].str.len() > 0].copy()
        scored["matched"] = scored["skills"].apply(lambda skills: len(my_skills & set(skills)))
        scored["skill_match"] = 100 * scored["matched"] / scored["skills"].str.len()
        scored["missing"] = scored["skills"].apply(lambda skills: sorted(set(skills) - my_skills))

        # Score 2 - meaning match: how close is your resume's embedding to the job's?
        similarity = semantic_similarity(resume_text)
        scored["meaning_match"] = scored["job_id"].map(similarity).fillna(0)

        # Final score: half skills, half meaning
        scored["match"] = (0.5 * scored["skill_match"] + 0.5 * scored["meaning_match"]).round()
        top = scored.sort_values(["match", "matched"], ascending=False).head(15)

        st.subheader("Best-matching jobs")
        st.caption("Match = 50% skill overlap + 50% meaning similarity (AI embeddings + pgvector).")
        percent = {"format": "%d%%", "min_value": 0, "max_value": 100}
        st.dataframe(
            top[["match", "skill_match", "meaning_match", "title", "company", "location", "missing", "url"]],
            column_config={
                "match": st.column_config.ProgressColumn("Match", **percent),
                "skill_match": st.column_config.NumberColumn("Skills", format="%d%%"),
                "meaning_match": st.column_config.NumberColumn("Meaning", format="%d%%"),
                "missing": "Skills you're missing",
                "url": st.column_config.LinkColumn("Apply", display_text="Open"),
            },
            hide_index=True,
            width="stretch",
        )

        gaps = Counter(s for missing in scored["missing"] for s in missing).most_common(10)
        if gaps:
            st.subheader("Top skills to learn next")
            st.caption("Skills most often required by these jobs that aren't in your resume.")
            gap_df = pd.DataFrame(gaps, columns=["skill", "jobs"])
            st.plotly_chart(px.bar(gap_df[::-1], x="jobs", y="skill", orientation="h",
                                   labels={"jobs": "Job postings", "skill": ""}),
                            width="stretch")

st.divider()
st.caption("Job data from [Adzuna](https://www.adzuna.com) (Jobs by Adzuna) and public company career pages "
           "(Greenhouse, Lever). Skills extracted with AI and may contain errors.")
