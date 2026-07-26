from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.services.golden.contracts import GoldenCaseManifest, GoldenManifestError


ALLOWED_PREFIXES = (
    "golden-data/inputs/",
    "golden-data/expected/",
    "golden-data/manifests/",
)


def load_golden_manifest(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> GoldenCaseManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = GoldenCaseManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exception:
        raise GoldenManifestError("golden_manifest_invalid") from exception
    root = Path(repo_root).resolve()
    for artifact in manifest.tracked_files:
        normalized = artifact.path.replace("\\", "/")
        if (
            normalized.startswith("/")
            or ".." in Path(normalized).parts
            or "private" in normalized.casefold()
            or not normalized.startswith(ALLOWED_PREFIXES)
        ):
            raise GoldenManifestError("golden_path_invalid")
        resolved = (root / normalized).resolve()
        try:
            resolved.relative_to(root / "golden-data")
        except ValueError as exception:
            raise GoldenManifestError("golden_path_invalid") from exception
    return manifest
