
from fastapi import FastAPI, UploadFile, File, HTTPException
from dataclasses import asdict

import config
from backend.resume_parser import ResumeParser, ParseError


app = FastAPI(
    title="ResumeIQ API",
    description="Backend API for ResumeIQ",
    version="1.0.0"
)


@app.get("/")
def home():
    return {"message": "Welcome to ResumeIQ API"}


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "application": "ResumeIQ"
    }


@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):

    file_name = file.filename or ""

    # Check file extension before reading
    suffix = (
        "." + file_name.rsplit(".", 1)[-1].lower()
        if "." in file_name else ""
    )

    if suffix not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF or DOCX resume."
        )

    try:
        # Read only up to the allowed size + 1 byte
        data = await file.read(int(config.MAX_UPLOAD_BYTES) + 1)

        # Reuse existing parser
        parsed = ResumeParser().parse(data, file_name)

        # Convert ParsedResume dataclass into JSON-compatible dict
        result = asdict(parsed)

        # Avoid returning full resume text in the API response
        result.pop("text", None)

        return {
            "success": True,
            "resume": result
        }

    except ParseError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    finally:
        await file.close()
