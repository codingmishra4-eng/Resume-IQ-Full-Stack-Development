import io
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.api_v1.settings import APISettings
from backend.api_v1 import upload_validation
from backend.resume_parser import ParsedResume, ResumeParser

URL = "/api/resume/upload"


def post(client, data, name="resume.docx", mime="application/octet-stream"):
    return client.post(URL, files={"file": (name, data, mime)})


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert set(response.json()) == {"detail", "code"}
    assert response.json()["code"] == code
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize("name", ["resume.docx", "RESUME.DOCX", r"C:\private\candidate.docx"])
def test_docx_upload(client, sample_resume_bytes, name):
    response = post(client, sample_resume_bytes, name)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["success"] is True
    assert result["resume"]["file_type"] == "docx"
    assert result["resume"]["file_name"] == "resume.docx"
    assert result["resume"]["word_count"] > 60
    assert "education" in result["resume"]["section_order"]


def test_pdf_upload(client, pdf_bytes):
    response = post(client, pdf_bytes, "candidate.pdf", "application/pdf")
    assert response.status_code == 200, response.text
    assert response.json()["resume"]["file_type"] == "pdf"
    assert response.json()["resume"]["pages"] == 1


@pytest.mark.parametrize("name", ["resume.exe", "resume.doc", "resume", "resume.pdf.exe"])
def test_unsupported_formats(client, name):
    assert_error(post(client, b"private contents", name), 400, "unsupported_format")


@pytest.mark.parametrize("name", ["resume.pdf", "resume.docx"])
def test_empty_file(client, name):
    assert_error(post(client, b"", name), 400, "empty_file")


@pytest.mark.parametrize("name,data", [
    ("resume.pdf", b"Not a PDF"),
    ("resume.docx", b"Not a Word document"),
    ("resume.pdf", b"%PDF-1.7 corrupted"),
])
def test_malformed_files(client, name, data):
    assert_error(post(client, data, name), 400, "invalid_file")


def test_mismatched_content(client, sample_resume_bytes, pdf_bytes):
    assert_error(post(client, sample_resume_bytes, "resume.pdf"), 400, "invalid_file")
    assert_error(post(client, pdf_bytes, "resume.docx"), 400, "invalid_file")


def test_missing_file_or_non_file_field(client):
    for response in (client.post(URL), client.post(URL, data={"file": "private input"})):
        assert_error(response, 422, "invalid_request")
        assert "private input" not in response.text


def test_exact_size_limit_and_one_byte_over(sample_resume_bytes):
    with TestClient(create_app(APISettings(max_upload_bytes=len(sample_resume_bytes)))) as client:
        assert post(client, sample_resume_bytes).status_code == 200
        assert_error(post(client, sample_resume_bytes + b"x"), 400, "file_too_large")


def test_oversize_never_reaches_parser(monkeypatch):
    def must_not_parse(*args):
        pytest.fail("Oversized file reached parser")
    monkeypatch.setattr(ResumeParser, "parse", must_not_parse)
    with TestClient(create_app(APISettings(max_upload_bytes=10))) as client:
        assert_error(post(client, b"x" * 11), 400, "file_too_large")
        # Also exercise the whole-request cap before multipart parsing.
        assert_error(post(client, b"x" * 70000), 400, "file_too_large")


def test_response_privacy(client, sample_resume_bytes):
    response = post(client, sample_resume_bytes, "personal-name.docx")
    assert response.status_code == 200
    metadata = response.json()["resume"]
    assert set(metadata) == {
        "file_name", "file_type", "pages", "word_count", "section_order",
        "bullet_count", "tables_detected", "images_detected", "headings_look_caps",
    }
    for forbidden in ("text", "contact", "emails", "phones", "links", "meta", "sections", "warnings"):
        assert forbidden not in metadata
    # Fixture data is synthetic; no user resume is needed to test privacy.
    for value in ("Priya", "priya.sharma@example.com", "98765", "Acme", "personal-name", "Forecasted"):
        assert value not in response.text


def test_allowlist_survives_future_parser_fields(client, monkeypatch):
    def fake_parse(self, data, name):
        result = ParsedResume(file_name="PRIVATE", file_type="pdf", text="PRIVATE", pages=1,
                              word_count=80, sections={"summary": "PRIVATE"}, contact={"email": "PRIVATE"},
                              section_order=["skills", "PRIVATE"], warnings=["PRIVATE"], meta={"name_guess": "PRIVATE"})
        result.future_personal_field = "PRIVATE"
        return result
    monkeypatch.setattr(ResumeParser, "parse", fake_parse)
    response = post(client, b"%PDF-1.7 fake", "PRIVATE.pdf")
    assert response.status_code == 200
    assert "PRIVATE" not in response.text
    assert response.json()["resume"]["section_order"] == ["skills"]


def test_unexpected_error_is_private(client, monkeypatch):
    def fail(*args):
        raise TypeError("PRIVATE resume text and credentials")
    monkeypatch.setattr(ResumeParser, "parse", fail)
    response = post(client, b"%PDF-1.7 fake", "private-name.pdf")
    assert_error(response, 500, "internal_error")
    assert "PRIVATE" not in response.text
    assert "private-name" not in response.text


def archive(entries, compression=ZIP_STORED):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=compression) as zip_file:
        for name, data in entries:
            zip_file.writestr(name, data)
    return buffer.getvalue()


def test_non_word_zip_rejected(client):
    data = archive([("private.txt", "private contents")])
    assert_error(post(client, data), 400, "invalid_file")


@pytest.mark.parametrize("kind", ["entries", "expanded", "ratio", "duplicate"])
def test_docx_archive_limits(client, monkeypatch, kind):
    entries = [("[Content_Types].xml", "x"), ("_rels/.rels", "x"), ("word/document.xml", "x")]
    compression = ZIP_STORED
    if kind == "entries":
        monkeypatch.setattr(upload_validation, "MAX_DOCX_ENTRIES", 2)
    elif kind == "expanded":
        monkeypatch.setattr(upload_validation, "MAX_DOCX_EXPANDED_BYTES", 2)
    elif kind == "ratio":
        compression = ZIP_DEFLATED
        entries[-1] = ("word/document.xml", "A" * 200000)
    else:
        entries.append(("word/document.xml", "duplicate"))
    assert_error(post(client, archive(entries, compression)), 400, "unsafe_document")


def test_upload_closed_even_when_rejected(monkeypatch):
    from starlette.datastructures import UploadFile
    closed = []
    original = UploadFile.close

    async def record_close(self):
        closed.append(self)
        await original(self)

    monkeypatch.setattr(UploadFile, "close", record_close)
    with TestClient(create_app(APISettings())) as client:
        assert post(client, b"content", "resume.exe").status_code == 400
    assert closed and all(file.file.closed for file in closed)


def test_encrypted_pdf_rejected(client):
    import pymupdf
    document = pymupdf.open()
    document.new_page().insert_text((40, 40), "Synthetic resume")
    data = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,
                           owner_pw="synthetic-owner", user_pw="synthetic-reader")
    document.close()
    assert_error(post(client, data, "resume.pdf"), 400, "invalid_file")


def test_sparse_document_rejected_without_parser_detail(client):
    from docx import Document
    document = Document()
    document.add_paragraph("Synthetic private content")
    buffer = io.BytesIO()
    document.save(buffer)
    response = post(client, buffer.getvalue())
    assert_error(response, 400, "invalid_file")
    assert "Synthetic" not in response.text


@pytest.mark.parametrize("extra", ["file", "other"])
def test_extra_upload_parts_rejected(client, sample_resume_bytes, extra):
    response = client.post(URL, files=[
        ("file", ("resume.docx", sample_resume_bytes)),
        (extra, ("second.docx", sample_resume_bytes)),
    ])
    assert_error(response, 400, "invalid_request")
