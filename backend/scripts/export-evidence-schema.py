import json
from pathlib import Path

from app.services.evidence.contracts import EvidenceManifest


OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "evidence"
    / "evidence-manifest.v1.schema.json"
)


def main() -> None:
    payload = json.dumps(
        EvidenceManifest.model_json_schema(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    OUTPUT_PATH.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
