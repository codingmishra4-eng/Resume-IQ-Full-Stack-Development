"""
Shared pytest fixtures: a tiny in-memory database and a real sample resume
(DOCX built with our own generator, then parsed back — a genuine round-trip).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.database import Database                    # noqa: E402
from resume_builder.builder import ResumeBuilder          # noqa: E402


@pytest.fixture()
def db(tmp_path) -> Database:
    """Dedicated SQLite file per test (no cross-test pollution)."""
    d = Database(url=f"sqlite:///{tmp_path / 'test.db'}")
    return d


@pytest.fixture()
def sample_resume_bytes(tmp_path) -> bytes:
    """A realistic DOCX resume produced by our DOCX generator."""
    data = {
        "full_name": "Priya Sharma", "headline": "Aspiring Data Analyst",
        "email": "priya.sharma@example.com", "phone": "+91 98765 43210",
        "location": "Bengaluru, India", "linkedin": "linkedin.com/in/priyasharma",
        "summary": ("Analytical learner with internship experiance in SQL and Python. "
                    "Worked on dashboards and was responsible for weekly reporting. "
                    "Enjoys turning messy data into clear decisions."),
        "skills": ["Python", "SQL", "Excel", "Power BI", "Pandas", "Statistics"],
        "experience": [{
            "role": "Data Intern", "company": "Acme Retail", "location": "Remote",
            "start": "Jun 2025", "end": "Aug 2025",
            "bullets": ["Responsible for weekly sales reporting dashboards",
                        "Helped with cleaning 3 datasets in pandas without metrics",
                        "Automated manual reporting, saving 6 hours per week"]}],
        "education": [{"degree": "B.Tech Computer Science", "institution": "VIT",
                       "location": "Vellore", "start": "2022", "end": "2026",
                       "details": "CGPA 8.6, coursework in statistics and DBMS"}],
        "projects": [{"name": "Sales Forecasting", "tech": "Prophet, Pandas",
                      "description": "Forecasted monthly sales with 12% MAPE on real data",
                      "link": "github.com/priyasharma/forecast"}],
        "certifications": [{"name": "Google Data Analytics", "issuer": "Coursera", "year": "2025"}],
        "achievements": ["Top 5% in university hackathon (600 participants)"],
        "languages": [{"name": "English", "level": "Fluent"}, {"name": "Hindi", "level": "Native"}],
        "interests": ["Chess", "Open-source"],
        "extra_sections": [],
    }
    builder = ResumeBuilder(out_dir=tmp_path / "gen")
    from resume_builder.resume_data import ResumeData
    path = builder.build(ResumeData.from_dict(data), "data-analyst", "docx")
    return path.read_bytes()


@pytest.fixture()
def builder(tmp_path) -> ResumeBuilder:
    return ResumeBuilder(out_dir=tmp_path / "gen")
