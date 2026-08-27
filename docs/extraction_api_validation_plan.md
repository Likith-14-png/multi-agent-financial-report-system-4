# Extraction API Validation Plan

## 1. Prerequisites

1. Start the Swagger API and identify its base URL, for example `http://localhost:8000`.
2. Set credentials without committing them:
   ```powershell
   $env:BASE_URL = "http://localhost:8000"
   $env:API_KEY = "<secret supplied by the API owner>"
   $env:API_KEY_HEADER = "Authorization"
   $env:API_KEY_PREFIX = "Bearer "
   ```
3. Confirm the read-only fixture exists at `C:\Users\rajan\Downloads\financial_cross_check_test_fixture.pdf`.
4. Install dependencies in the selected Python environment:
   ```powershell
   python -m pip install requests PyPDF2
   ```

## 2. Test Execution Strategy

1. Read the PDF with `PyPDF2` and extract text page by page. The fixture is opened read-only.
2. Identify metric/value occurrences, page numbers, nearby section headings, and report years.
3. Select the expected occurrence per metric. Primary financial-statement sections receive priority over notes, risk, and narrative sections; the original occurrence text and page are retained.
4. Send one `POST /analysis/upload` request with the PDF, company name, and report year.
5. Require a successful JSON response containing `analysis_id`.
6. Send one `GET /analysis/{analysis_id}/extraction` request.
7. Validate the response schema: `metrics` must be a list, each metric must have a value, and provenance must include source file, page, chunk ID, and section when the API provides them.
8. Compare numeric value, unit, and currency against the selected PDF occurrence. Preserve formatting differences such as commas while comparing numeric meaning.
9. Record missing metrics, value mismatches, missing provenance, HTTP failures, timeouts, malformed JSON, and schema mismatches.
10. Write the complete result to a JSON report and return a non-zero process exit code when validation fails.

## 3. Safety Rules

- The PDF is never written to or modified.
- The script uses only upload and extraction GET endpoints.
- No DELETE, PUT, or other destructive request is made.
- API keys are read from environment variables/arguments and never written to the report or printed.
- Use a test collection or cleanup policy approved by the API owner if uploads persist server-side.

## 4. Command

From the repository root:

```powershell
python tools/validate_extraction_api.py
```

Optional overrides:

```powershell
python tools/validate_extraction_api.py `
  --pdf "C:\path\to\report.pdf" `
  --base-url "$env:BASE_URL" `
  --api-key "$env:API_KEY" `
  --company-name "Example Company" `
  --report-year 2025 `
  --report validation.json
```

## 5. Exit Codes

- `0`: API request and all detected metric comparisons passed.
- `1`: API returned data, but one or more comparisons/provenance checks failed.
- `2`: Configuration, file access, HTTP, timeout, JSON, or schema error.

## 6. Validation Report

The script writes the JSON report specified by `--report` or `VALIDATION_REPORT`. It contains page count, selected expected occurrences, API status, checked metrics, and discrepancy details.
