from pathlib import Path


def resolve_chroma_db_path(script_file: str | Path | None = None, workspace_root: str | Path | None = None) -> Path:
    """Resolve the ChromaDB storage directory consistently across scripts."""
    script_path = Path(script_file or __file__).resolve()
    project_root = script_path.parent.parent if script_path.parent.name == "scripts" else script_path.parent
    workspace_path = Path(workspace_root).resolve() if workspace_root else project_root.parent

    candidate_paths = []
    if workspace_path:
        candidate_paths.append(workspace_path / "enterprise_chroma_db")
    candidate_paths.append(project_root / "enterprise_chroma_db")
    candidate_paths.append(script_path.parent / "enterprise_chroma_db")

    for candidate in candidate_paths:
        if candidate.exists() and (candidate / "chroma.sqlite3").exists():
            return candidate

    for candidate in candidate_paths:
        if candidate.exists():
            return candidate

    return candidate_paths[0]
