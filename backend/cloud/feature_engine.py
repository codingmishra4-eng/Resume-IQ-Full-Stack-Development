"""Reuse local engines without SQLite persistence or raw-text cloud logging."""
from dataclasses import replace
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import config
from backend.ats_analyzer import ATSAnalyzer
from backend.grammar_checker import MISSPELLINGS, FILLER_INTENSIFIERS
from backend.job_matcher import JobMatcher, STOP_WORDS
from backend.ai_assistant import AIAssistant
from backend.resume_parser import ResumeParser, ParseError
from backend.api_v1.upload_validation import validate_content
from backend.api_v1.errors import APIError
from backend.cloud.feature_schemas import Report, MatchResult, ATS, Writing, DraftInput, Template, Suggestion
from resume_builder.template_manager import get_template_manager
from resume_builder.resume_data import ResumeData
from resume_builder.pdf_generator import ResumePDFGenerator
from resume_builder.docx_generator import ResumeDOCXGenerator

TEMPLATE_MAP = {'essential': 'ats-minimal', 'editorial': 'executive', 'compact': 'engineering'}


def templates():
    registry = get_template_manager()
    return [Template(id=id, name=id.title(), backend_id=backend,
                     description=registry.get(backend).description) for id, backend in TEMPLATE_MAP.items()]


def parse_original(data, suffix):
    validate_content(data, suffix)
    try:
        parsed = ResumeParser().parse(data, 'resume' + suffix)
    except (ParseError, ValueError, RuntimeError):
        raise APIError('invalid_file', 'The stored document could not be read.') from None
    if len(parsed.text) > 100000 or parsed.pages > 100:
        raise APIError('analysis_limit', 'Use a document with at most 100 pages and 100,000 extracted characters.')
    return parsed


def match_resume(parsed, jd):
    result = JobMatcher().match(parsed, jd)
    # Return taxonomy evidence and keyword coverage, never the sensitive raw JD/title.
    tokens = [word for word in re.findall(r'[a-z][a-z+#./-]{3,}', jd.lower()) if word not in STOP_WORDS]
    frequency = {word: tokens.count(word) for word in dict.fromkeys(tokens)}
    jd_skills = {skill for values in result.jd_categories.values() for skill in values}
    common = [word for word, count in sorted(frequency.items(), key=lambda item: -item[1])
              if count >= 2 and word not in jd_skills and len(word) > 3][:25]
    matched = [word for word in common if word in parsed.text.lower()]
    return MatchResult(match_score=result.match_score, matching=result.matching, partial=result.partial,
        missing=result.missing, jd_extra_keywords=result.jd_extra_keywords, keyword_matching=matched,
        resume_categories=result.resume_categories, jd_categories=result.jd_categories, notes=result.notes,
        explanation='Taxonomy skill coverage counts exact hits as 1 and related-category partial hits as 0.5. When repeated JD keywords exist, weight skills 70% and keyword coverage 30%; otherwise use skills only. This is a heuristic estimate, not a hiring prediction.')


def analyze_resume(parsed, jd=None):
    engine = ATSAnalyzer()
    result = engine.analyze(parsed, job_description=jd)
    payload = result.as_dict()
    writing = payload['writing']
    # Findings are bounded excerpts required for review, not the original document.
    for key in ('spelling', 'grammar', 'weak_phrasings'):
        writing[key] = [{**item, 'context': item['context'][:400]} for item in writing[key][:40]]
    writing['long_sentences'] = [value[:400] for value in writing['long_sentences'][:10]]
    writing['repeated_words'] = writing['repeated_words'][:30]
    ats = ATS(overall=result.overall, categories=payload['categories'], strengths=result.strengths[:30],
              weaknesses=result.weaknesses[:30], recommendations=result.recommendations[:30], writing=Writing(**writing))
    return Report(ats=ats, impact=engine._quantified_bullets(parsed), sections=parsed.section_order,
                  contact={key: bool(parsed.contact.get(key)) for key in ('email','phone','linkedin')},
                  keywords=result.keywords.all_matched if result.keywords else [],
                  job_match=match_resume(parsed, jd) if jd else None,
                  template_ids=list(TEMPLATE_MAP), disclaimer=result.verified_notes['disclaimer'])


def conservative_edit(value):
    """Spelling, filler removal and contribution-level phrasing only; no new claims."""
    value = re.sub(r'\b[A-Za-z]+\b', lambda m: MISSPELLINGS.get(m.group().lower(), m.group()), value)
    value = re.sub(r'\b(?:' + '|'.join(map(re.escape, FILLER_INTENSIFIERS)) + r')\s+', '', value, flags=re.I)
    value = re.sub(r'\bworked on\b', 'contributed to', value, flags=re.I)
    value = re.sub(r'\bhelped with\b', 'supported', value, flags=re.I)
    return value.strip()


def make_assistant(enabled):
    cfg = config.AIConfig()
    cfg.timeout_seconds, cfg.max_tokens = 12, 600
    if not enabled:
        cfg.api_key = None
    assistant = AIAssistant(cfg)
    if assistant.ai_available and hasattr(assistant._client, 'with_options'):
        assistant._client = assistant._client.with_options(max_retries=0)
    return assistant


def improve_resume(parsed, request, ai_enabled):
    source = request.text.strip()
    if source and source.casefold() not in parsed.text.casefold():
        raise APIError('ungrounded_input', 'Choose text copied exactly from this resume.')
    if not source:
        source = parsed.sections.get('summary', '')[:6000] if request.kind == 'summary' else '\n'.join(
            line.strip() for line in parsed.text.splitlines() if re.match(r'^\s*[•●▪*-]', line))[:6000]
    assistant = make_assistant(ai_enabled and request.use_ai)
    output = []
    if request.kind == 'keywords':
        if not request.job_description:
            raise APIError('invalid_request', 'A job description is required for keyword guidance.')
        match = match_resume(parsed, request.job_description)
        # Guidance never asserts missing skills as experience or sends the JD to AI.
        output = [Suggestion(kind='keyword', original=skill, improved=f'Only include {skill} if you genuinely have it. Otherwise plan learning or a real project before listing it.',
                             rationale='This JD skill is not an exact resume match.', source='rule-based')
                  for skill in (match.missing + match.partial)[:12]]
    elif request.kind == 'verbs':
        for item in assistant.suggest_verbs(source):
            output.append(Suggestion(kind='phrasing', original=item.original, improved=conservative_edit(item.original),
                                     rationale='Consider these alternatives only if accurate: ' + item.improved + '. ' + item.rationale,
                                     source='rule-based'))
    else:
        chunks = [source] if request.kind == 'summary' else [line.strip().lstrip('•*- ').strip() for line in source.splitlines() if line.strip()][:6]
        candidates = []
        if assistant.ai_available and source:
            try:
                candidates = [assistant.rewrite_summary(source, source)] if request.kind == 'summary' else assistant.improve_bullets(chunks, source)
            except Exception:
                candidates = []
        normalize = lambda value: re.findall(r'[\w%]+', value.casefold())
        for original in chunks:
            if not original:
                continue
            improved = conservative_edit(original)
            candidate = next((item for item in candidates if item.original.strip() == original), None)
            # Only accept source-preserving proof edits. Free generation could
            # invent roles or reorder facts despite containing known vocabulary.
            accepted = bool(candidate and candidate.source == 'openai' and len(candidate.improved) <= 8000
                            and normalize(candidate.improved) in (normalize(original), normalize(improved)))
            output.append(Suggestion(kind=request.kind, original=original,
                improved=candidate.improved if accepted else improved,
                rationale='Source-preserving proof edit; review before use.' if accepted else 'Conservative spelling/wording edit. Unsupported generated claims are discarded; no metrics or experience added.',
                source='openai' if accepted else 'rule-based'))
    return output


def export_draft(payload: DraftInput, fmt):
    data = payload.draft
    # Free-form experience/education stay literal text; do not infer employers,
    # dates, degrees or titles the user never supplied.
    resume = ResumeData(full_name=data.name, headline=data.title, email=data.email,
                        phone=data.phone, location=data.location, summary=data.summary,
                        skills=[item.strip() for item in re.split(r'[,\n]', data.skills) if item.strip()],
                        extra_sections=[{'title': label, 'body': content} for label, content in
                                        [('Experience', data.experience), ('Education', data.education)] if content])
    template = get_template_manager().get(TEMPLATE_MAP[payload.template])
    template = replace(template, section_order=['summary','skills'])
    with TemporaryDirectory(prefix='resumeiq-export-') as directory:
        path = Path(directory) / ('resume.' + fmt)
        generator = ResumePDFGenerator() if fmt == 'pdf' else ResumeDOCXGenerator()
        generator.generate(resume, template, path)
        if path.stat().st_size > 5 * 1024 * 1024:
            raise APIError('export_limit', 'Generated export exceeds the size limit.')
        return path.read_bytes()
