"""Explicit bounded cloud feature contracts; no raw document/JD/prompts in lists."""
import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


Text = Annotated[str, StringConstraints(max_length=2000)]
JD = Annotated[str, StringConstraints(strip_whitespace=True, min_length=30, max_length=20000)]
Score = Annotated[float, Field(ge=0, le=100)]


class AnalyzeInput(Model):
    job_description: JD | None = None


class MatchInput(Model):
    job_description: JD


class Check(Model):
    status: Literal['pass','warn','fail']
    label: Text
    detail: Text = ''


class Category(Model):
    name: str
    score: Score
    weight: float = Field(ge=0, le=1)
    checks: list[Check] = Field(max_length=50)


class WritingIssue(Model):
    kind: str
    message: Text
    context: Text
    suggestion: Text = ''


class Writing(Model):
    spelling: list[WritingIssue]
    grammar: list[WritingIssue]
    weak_phrasings: list[WritingIssue]
    long_sentences: list[Text]
    passive_count: int
    buzzwords: list[str]
    repeated_words: list[tuple[str,int]]


class ATS(Model):
    overall: Score
    categories: dict[str,Category]
    strengths: list[Text]
    weaknesses: list[Text]
    recommendations: list[Text]
    writing: Writing


class MatchResult(Model):
    match_score: Score
    matching: list[str]
    partial: list[str]
    missing: list[str]
    jd_extra_keywords: list[str]
    keyword_matching: list[str]
    resume_categories: dict[str,list[str]]
    jd_categories: dict[str,list[str]]
    notes: list[Text]
    explanation: str


class Impact(Model):
    count: int = Field(ge=0)
    bullets: int = Field(ge=0)


class Report(Model):
    ats: ATS
    impact: Impact
    sections: list[str]
    contact: dict[str,bool]
    keywords: list[str]
    job_match: MatchResult | None
    template_ids: list[str]
    disclaimer: str


class AnalysisRecord(Model):
    id: UUID
    resume_id: UUID
    created_at: datetime
    report: Report


class RecordSummary(Model):
    id: UUID
    resume_id: UUID
    created_at: datetime
    ats_score: Score | None


class MatchRecord(Model):
    id: UUID
    resume_id: UUID
    created_at: datetime
    result: MatchResult


class ImproveInput(Model):
    kind: Literal['summary','bullets','verbs','keywords']
    text: str = Field(default='', max_length=6000)
    job_description: JD | None = None
    use_ai: bool = False


class Suggestion(Model):
    kind: str
    original: str = Field(max_length=6000)
    improved: str = Field(max_length=8000)
    rationale: Text
    source: Literal['openai','rule-based']


class Improvements(Model):
    items: list[Suggestion]
    provider_used: bool
    notice: str


class DraftData(Model):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    title: str = Field(default='', max_length=200)
    email: str = Field(default='', max_length=254)
    phone: str = Field(default='', max_length=100)
    location: str = Field(default='', max_length=200)
    summary: str = Field(default='', max_length=5000)
    experience: str = Field(default='', max_length=15000)
    education: str = Field(default='', max_length=5000)
    skills: str = Field(default='', max_length=3000)

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Invalid email')
        return value

    @field_validator('*', mode='after')
    @classmethod
    def clean(cls, value):
        # python-docx XML and PDF text must not receive control characters.
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value):
            raise ValueError('Unsupported text characters')
        return value.strip()


class DraftInput(Model):
    template: Literal['essential','editorial','compact']
    draft: DraftData


class DraftRecord(DraftInput):
    id: UUID
    created_at: datetime
    updated_at: datetime


class DraftSummary(Model):
    id: UUID
    template: str
    created_at: datetime
    updated_at: datetime


class Template(Model):
    id: str
    name: str
    backend_id: str
    description: str
    layout: Literal['single'] = 'single'
