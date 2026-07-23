from uuid import UUID

from app.services.evidence.contracts import (
    EngineVersion,
    EvidenceItem,
    ExcelCellLocation,
)


ASSET_ID = UUID("019f4000-0000-7000-8000-000000000001")
MODEL_ID = UUID("019f4000-0000-7000-8000-000000000002")
PROVIDER_ID = UUID("019f4000-0000-7000-8000-000000000003")
CREDENTIAL_ID = UUID("019f4000-0000-7000-8000-000000000004")
PROJECT_ID = UUID("019f4000-0000-7000-8000-000000000005")
USER_ID = UUID("019f4000-0000-7000-8000-000000000006")
BRIEF_GROUP_ID = UUID("019f4000-0000-7000-8000-000000000007")
EVIDENCE_ID = f"e-{'1' * 64}"
ASSET_VERSION = f"sha256:{'2' * 64}"


def source_evidence(*, raw_value: str = "销售额为 12000 CNY") -> EvidenceItem:
    return EvidenceItem(
        evidence_id=EVIDENCE_ID,
        evidence_type="source_fact",
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        location=ExcelCellLocation(kind="excel_cell", sheet="销售", cell="B2"),
        raw_value=raw_value,
        normalized_value="12000",
        value_kind="number",
        unit="CNY",
        currency="CNY",
        parser_name="xlsx-safe",
        parser_version="1.0.0",
    )


def inferred_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"e-{'3' * 64}",
        evidence_type="ai_inference",
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        location=ExcelCellLocation(kind="excel_cell", sheet="销售", cell="B2"),
        raw_value="销售势头稳定",
        normalized_value=None,
        value_kind="narrative",
        unit=None,
        currency=None,
        parser_name="xlsx-safe",
        parser_version="1.0.0",
        inference_model=EngineVersion(name="agnes-2.0-flash", version="1"),
    )


def valid_brief_payload() -> dict:
    return {
        "module": "ppt",
        "goal": "形成月度销售经营复盘",
        "audience": "销售管理层",
        "language": "zh-CN",
        "domain": "sales",
        "tone": "professional",
        "source_asset_versions": [
            {
                "asset_id": str(ASSET_ID),
                "asset_version": ASSET_VERSION,
            }
        ],
        "term_library_versions": [],
        "selected_skills": [
            {
                "skill_code": "ppt.sales-business-review.v1",
                "version": "1.0.0",
            }
        ],
        "selected_model": {
            "model_id": str(MODEL_ID),
            "provider_id": str(PROVIDER_ID),
            "credential_id": str(CREDENTIAL_ID),
            "model_code": "agnes-2.0-flash",
        },
        "output_plan": {
            "deliverables": [
                {
                    "kind": "pptx",
                    "title": "销售经营汇报",
                    "source": "system_default",
                    "evidence_ids": [],
                }
            ]
        },
        "facts": [
            {
                "content": "销售额为 12000 CNY",
                "source": "file",
                "evidence_ids": [EVIDENCE_ID],
            }
        ],
        "inferences": [
            {
                "content": "销售势头稳定",
                "source": "agnes_inference",
                "evidence_ids": [EVIDENCE_ID],
            }
        ],
        "unresolved_items": [],
        "must_include": [
            {
                "content": "销售额",
                "source": "user",
                "evidence_ids": [],
            }
        ],
        "must_exclude": [],
        "citation_policy": {
            "internal_tracking": True,
            "visible_citations": True,
        },
    }
