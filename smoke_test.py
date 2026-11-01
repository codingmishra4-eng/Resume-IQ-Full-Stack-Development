"""Dev-only smoke test: exercise parser, analyzer, matcher, and all 15 templates."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from backend.scoring_engine import ScoringEngine
from resume_builder.builder import ResumeBuilder
from resume_builder.resume_data import ResumeData

OUT = root / "smoke_out"
OUT.mkdir(exist_ok=True)

resume = ResumeData.from_dict({
    "full_name": "Priya Sharma", "headline": "Aspiring Data Analyst",
    "email": "priya.sharma@example.com", "phone": "+91 98765 43210",
    "location": "Bengaluru, India", "linkedin": "linkedin.com/in/priyasharma",
    "summary": "Analytical and detail-oriented data enthusiastic with internship experiance in SQL and Python. Worked on dashboards and was responsible for reporting.",
    "skills": ["Python", "SQL", "Excel", "Power BI", "Pandas", "Statistics"],
    "experience": [{"role": "Data Intern", "company": "Acme Retail",
                    "location": "Remote", "start": "Jun 2025", "end": "Aug 2025",
                    "bullets": ["Responsible for weekly sales reporting dashboards",
                                "Helped with cleaning 3 datasets in pandas missing metrics"]}],
    "education": [{"degree": "B.Tech Computer Science", "institution": "VIT",
                   "location": "Vellore", "start": "2022", "end": "2026",
                   "details": "CGPA 8.6, Coursework in statistics and DBMS"}],
    "projects": [{"name": "Sales Forecasting", "tech": "Prophet, Pandas",
                  "description": "Forecasted monthly sales with 12% MAPE on real dataset", "link": "github.com/priyasharma/forecast"}],
    "certifications": [{"name": "Google Data Analytics", "issuer": "Coursera", "year": "2025"}],
    "achievements": ["Top 5% in university hackathon (600 participants)"],
    "languages": [{"name": "English", "level": "Fluent"}, {"name": "Hindi", "level": "Native"}],
})

builder = ResumeBuilder(out_dir=OUT)
print(f"[templates] {len(builder.list_templates())} registered")

# 1) render all 15 templates to PDF + DOCX + HTML
for tpl in builder.list_templates():
    pdf = builder.build(resume, tpl.id, "pdf")
    docx = builder.build(resume, tpl.id, "docx")
    html = builder.preview_html(resume, tpl.id)
    assert pdf.exists() and pdf.stat().st_size > 1500, f"PDF too small for {tpl.id}"
    assert docx.exists() and docx.stat().st_size > 1500, f"DOCX too small for {tpl.id}"
    assert "<html" in html.lower()
    print(f"OK {tpl.id:18s} pdf={pdf.stat().st_size//1024}kB docx={docx.stat().st_size//1024}kB")

# 2) parse back the DOCX (round-trip) and analyze
from backend.resume_parser import ResumeParser
docx_path = list(OUT.glob("*data-analyst.docx"))[0]
data = docx_path.read_bytes()
parsed = ResumeParser().parse(data, "priya_data_analyst.docx")
print(f"[parser] type={parsed.file_type} words={parsed.word_count} sections={parsed.section_order}")
assert parsed.word_count > 80
assert "education" in parsed.sections, f"missing education; sections={parsed.section_order}"

# 3) full analysis + job match
engine = ScoringEngine()
analysis = engine.analyze_upload(data, "priya_data_analyst.docx",
                                 job_description="Data Analyst — 2 years SQL dashboards Python "
                                                 "statistics communication Tableau reports ETL",
                                 persist=False)
print(f"[score] overall={analysis.overall}")
print(f"[scores] {analysis.category_scores}")
print(f"[job] match={analysis.job_match.match_score}% missing={analysis.job_match.missing}")
assert 0 <= analysis.overall <= 100

# 4) PDF report
from resume_builder.report_pdf import ReportPDFBuilder
rep = analysis.report_dict()
path = ReportPDFBuilder().build(rep, OUT / "analysis_report.pdf")
print(f"[report] {path} ({path.stat().st_size//1024} kB)")

print("SMOKE OK")
