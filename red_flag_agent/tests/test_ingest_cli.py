import subprocess
import sys
from pathlib import Path


def test_ingest_cli_reports_collection_and_counts(tmp_path: Path) -> None:
    source_path = tmp_path / "sample_report.txt"
    source_path.write_text(
        "Acme Corp annual report. Revenue improved this year.\n\n"
        "Cash flow remained healthy and liabilities were controlled.",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "ingest.py",
            "--file",
            str(source_path),
            "--company",
            "Acme Corp",
            "--collection",
            "cli_test_collection",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Collection name:" in result.stdout
    assert "Number of inserted chunks:" in result.stdout
    assert "Number of skipped duplicate chunks:" in result.stdout
    assert "cli_test_collection" in result.stdout
