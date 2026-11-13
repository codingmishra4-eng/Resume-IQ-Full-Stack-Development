import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.api_v1.settings import APISettings


@pytest.fixture
def client():
    with TestClient(create_app(APISettings()), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def pdf_bytes():
    doc = pymupdf.open()
    page = doc.new_page()
    text = "Synthetic Candidate\nprivate@example.invalid\nSkills\n" + ("Python SQL testing development teamwork delivery " * 20)
    page.insert_textbox(pymupdf.Rect(40, 40, 550, 780), text)
    data = doc.tobytes()
    doc.close()
    return data
