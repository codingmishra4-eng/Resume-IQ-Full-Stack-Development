from backend.api import app


def test_original_get_endpoints(client):
    assert client.get("/").status_code == 200
    assert client.get("/").json() == {"message": "Welcome to ResumeIQ API"}
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").json() == {"status": "ok", "application": "ResumeIQ"}
    assert app.title == "ResumeIQ API"


def test_openapi_contracts(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/resume/upload"]["post"]
    assert operation["requestBody"]["required"] is True
    form = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    form_schema = schema["components"]["schemas"][form["$ref"].split("/")[-1]]
    assert form_schema["required"] == ["file"]
    assert form_schema["properties"]["file"]["format"] == "binary"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("ResumeUploadResponse")
    for code in ("400", "422", "500"):
        assert operation["responses"][code]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorResponse")


def test_http_errors_are_consistent(client):
    for response in (client.get("/does-not-exist"), client.put("/api/health")):
        assert set(response.json()) == {"detail", "code"}
        assert response.json()["code"] == "http_error"
