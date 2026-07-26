from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.golden.contracts import GoldenManifestError, GoldenRegressionError
from app.services.golden.runner import GoldenRegressionRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = GoldenRegressionRunner(repo_root=args.repo_root).run(args.manifest)
    except (GoldenManifestError, GoldenRegressionError) as exception:
        print(json.dumps({"status": "blocked", "error": str(exception)}))
        return 1
    print(report.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
