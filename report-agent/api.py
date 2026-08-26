from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import subprocess
import sys

app = FastAPI(
    title="Financial Report Agent API",
    description="API for generating financial research reports",
    version="1.0.0"
)


OUTPUT_FILE = Path("../output/financial_report.pdf")


@app.get("/")
def home():
    return {
        "message": "Financial Report Agent API is running",
        "swagger": "/docs"
    }


@app.post("/generate-report")
def generate_report():
    try:
        # Run your existing Report Agent
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=result.stderr
            )

        if not OUTPUT_FILE.exists():
            raise HTTPException(
                status_code=500,
                detail="Report was not generated."
            )

        return {
            "status": "success",
            "message": "Financial report generated successfully",
            "file": str(OUTPUT_FILE)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/download-report")
def download_report():
    if not OUTPUT_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Financial report not found. Generate the report first."
        )

    return FileResponse(
        path=OUTPUT_FILE,
        media_type="application/pdf",
        filename="financial_report.pdf"
    )