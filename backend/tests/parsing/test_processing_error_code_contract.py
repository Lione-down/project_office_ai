from pathlib import Path

from app.workers.asset_processing import processing_contracts


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SECTION_HEADING = "### T2-001/T2-002 可持久化处理错误码"


def test_api_processing_error_codes_match_persisted_worker_contract() -> None:
    lines = (PROJECT_ROOT / "docs" / "API.md").read_text(encoding="utf-8").splitlines()
    section_start = lines.index(SECTION_HEADING)
    section_end = next(
        index
        for index, line in enumerate(lines[section_start + 1 :], section_start + 1)
        if line.startswith("## ")
    )
    documented_codes = {
        columns[1].strip().strip("`")
        for line in lines[section_start + 1 : section_end]
        if line.startswith("|")
        and len(columns := line.split("|")) >= 3
        and columns[1].strip().startswith("`")
    }

    assert documented_codes == processing_contracts.PERSISTED_PROCESSING_ERROR_CODES
