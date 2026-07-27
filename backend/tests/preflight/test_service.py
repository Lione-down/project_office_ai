from decimal import Decimal
from datetime import UTC, datetime
from hashlib import sha256
import json

import pytest
from sqlalchemy import select

from app.models.ai_models import AiModel
from app.models.briefs import Brief
from app.models.file_assets import FileAsset
from app.services.briefs.errors import BriefOperationError
from app.services.evidence.contracts import (
    EngineVersion,
    EvidenceManifest,
    ExcelCellLocation,
    ManifestIssue,
)
from app.services.preflight.catalog import PPT_DEFAULT_TEMPLATE
from app.services.preflight.contracts import (
    BriefRevisionCommand,
    ConflictResolution,
    PreflightCommand,
    TemplateVersion,
)
from tests.briefs.helpers import (
    ASSET_ID,
    ASSET_VERSION,
    EVIDENCE_ID,
    MODEL_ID,
    USER_ID,
    source_evidence,
)
from tests.preflight.conftest import BRIEF_ID


def _set_content(brief: Brief, content: dict) -> None:
    brief.content = content
    brief.content_checksum = sha256(
        json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


@pytest.mark.asyncio
async def test_owner_can_read_a_brief_revision(preflight_harness) -> None:
    snapshot = await preflight_harness.service.get("access-token", BRIEF_ID)

    assert snapshot.brief_id == BRIEF_ID
    assert snapshot.revision == 1
    assert snapshot.status == "draft"


@pytest.mark.asyncio
async def test_other_user_cannot_read_a_brief_revision(preflight_harness) -> None:
    with pytest.raises(BriefOperationError) as error:
        await preflight_harness.service.get("other-token", BRIEF_ID)

    assert error.value.error_code == "brief_not_found"


@pytest.mark.asyncio
async def test_revision_appends_user_edits_and_preserves_old_snapshot(
    preflight_harness,
) -> None:
    revised = await preflight_harness.service.revise(
        "access-token",
        BRIEF_ID,
        BriefRevisionCommand(
            expected_revision=1,
            goal="形成董事会季度销售复盘",
            template_versions=(
                TemplateVersion(
                    template_code=PPT_DEFAULT_TEMPLATE,
                    version="1.0.0",
                ),
            ),
        ),
    )

    async with preflight_harness.session_factory() as session:
        revisions = list(await session.scalars(select(Brief).order_by(Brief.revision)))
    assert revised.revision == 2
    assert revised.content.goal == "形成董事会季度销售复盘"
    assert revisions[0].content["goal"] == "形成月度销售经营复盘"
    assert revisions[0].source_snapshot.get("template_versions") is None
    assert (
        revisions[1].source_snapshot["source_asset_versions"]
        == revisions[0].source_snapshot["source_asset_versions"]
    )
    assert revisions[1].source_snapshot["template_versions"] == [
        {
            "template_code": PPT_DEFAULT_TEMPLATE,
            "version": "1.0.0",
        }
    ]


@pytest.mark.asyncio
async def test_stale_revision_cannot_append_a_competing_revision(
    preflight_harness,
) -> None:
    await preflight_harness.service.revise(
        "access-token",
        BRIEF_ID,
        BriefRevisionCommand(expected_revision=1, audience="区域总经理"),
    )

    with pytest.raises(BriefOperationError) as error:
        await preflight_harness.service.revise(
            "access-token",
            BRIEF_ID,
            BriefRevisionCommand(expected_revision=1, audience="董事会"),
        )

    assert error.value.error_code == "brief_revision_stale"


@pytest.mark.asyncio
async def test_clean_preflight_returns_plan_without_reserving_credits(
    preflight_harness,
) -> None:
    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )
    assert result.status == "preflight"
    assert result.estimated_credits == 800
    assert result.credit_multiplier == Decimal("1.0000")
    assert result.has_blockers is False
    assert result.outputs[0].template_code == PPT_DEFAULT_TEMPLATE
    async with preflight_harness.session_factory() as session:
        brief = await session.get(Brief, BRIEF_ID)
    assert brief.status == "preflight"
    assert brief.estimated_credits is None
    assert brief.preflight_snapshot["credit_multiplier"] == "1.0000"


@pytest.mark.asyncio
async def test_preflight_only_reports_referenced_unit_blockers_once(
    preflight_harness,
) -> None:
    unreferenced_evidence_id = f"e-{'9' * 64}"
    referenced = source_evidence().model_copy(
        update={
            "unit": None,
            "currency": None,
            "calculation_blocked": True,
            "warnings": ("numeric_unit_unknown",),
        }
    )
    unreferenced = referenced.model_copy(
        update={
            "evidence_id": unreferenced_evidence_id,
            "location": ExcelCellLocation(kind="excel_cell", sheet="销售", cell="B3"),
        }
    )
    manifest = EvidenceManifest(
        schema_version="evidence-manifest.v1",
        manifest_id=f"m-{'5' * 64}",
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        generated_at=datetime(2026, 7, 23, 23, 30, tzinfo=UTC),
        generator=EngineVersion(name="office-ai-evidence", version="1.0.0"),
        source_parser=EngineVersion(name="xlsx-safe", version="1.0.0"),
        evidence=(referenced, unreferenced),
        blockers=(
            ManifestIssue(code="numeric_unit_unknown", evidence_id=EVIDENCE_ID),
            ManifestIssue(
                code="numeric_unit_unknown",
                evidence_id=unreferenced_evidence_id,
            ),
        ),
    )
    stored = preflight_harness.manifest_store.write(USER_ID, ASSET_ID, manifest)
    async with preflight_harness.session_factory() as session, session.begin():
        asset = await session.get(FileAsset, ASSET_ID)
        asset.manifest_sha256 = stored.sha256

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )

    blocking = [item for item in result.conflicts if item.level == "blocking"]
    assert [(item.code, item.evidence_ids) for item in blocking] == [
        ("unit_unknown", (EVIDENCE_ID,))
    ]
    assert "工作表“销售”单元格 B2" in blocking[0].message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    ["unit_unknown", "numeric_low_confidence", "source_conflict"],
)
async def test_unresolved_data_blockers_cannot_reach_confirmation(
    preflight_harness, code: str
) -> None:
    async with preflight_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID)
        _set_content(
            brief,
            {
                **brief.content,
                "unresolved_items": [
                    {
                        "code": code,
                        "content": "请确认该数据后继续",
                        "source": "file",
                        "evidence_ids": [EVIDENCE_ID],
                        "blocking": True,
                    }
                ],
            },
        )

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )

    assert result.status == "needs_resolution"
    assert result.has_blockers is True
    assert [(item.code, item.level) for item in result.conflicts] == [
        (code, "blocking")
    ]
    assert result.conflicts[0].message.startswith("请")


@pytest.mark.asyncio
async def test_nonblocking_item_requires_confirmation_without_blocking_queue(
    preflight_harness,
) -> None:
    async with preflight_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID)
        _set_content(
            brief,
            {
                **brief.content,
                "unresolved_items": [
                    {
                        "code": "narrative_low_confidence",
                        "content": "请确认经营建议表述",
                        "source": "agnes_inference",
                        "evidence_ids": [EVIDENCE_ID],
                        "blocking": False,
                    }
                ],
            },
        )

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )

    assert result.status == "preflight"
    assert result.has_blockers is False
    assert [(item.code, item.level) for item in result.conflicts] == [
        ("narrative_low_confidence", "needs_confirmation")
    ]


@pytest.mark.asyncio
async def test_known_combined_skills_report_the_shared_input_auto_merge(
    preflight_harness,
) -> None:
    async with preflight_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID)
        combined = {
            **brief.content,
            "module": "combined",
            "selected_skills": [
                *brief.content["selected_skills"],
                {
                    "skill_code": "excel.sales-analysis-dashboard.v1",
                    "version": "1.0.0",
                },
            ],
            "output_plan": {
                "deliverables": [
                    *brief.content["output_plan"]["deliverables"],
                    {
                        "kind": "xlsx",
                        "title": "销售数据分析与经营看板",
                        "source": "system_default",
                        "evidence_ids": [],
                    },
                ]
            },
        }
        _set_content(brief, combined)
        brief.source_snapshot = {
            **brief.source_snapshot,
            "module": "combined",
            "selected_skills": combined["selected_skills"],
        }

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )

    assert result.estimated_credits == 1600
    assert ("skill_inputs_shared", "auto_merge") in [
        (item.code, item.level) for item in result.conflicts
    ]


@pytest.mark.asyncio
async def test_explicit_resolution_removes_the_matching_source_conflict(
    preflight_harness,
) -> None:
    async with preflight_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID)
        _set_content(
            brief,
            {
                **brief.content,
                "unresolved_items": [
                    {
                        "code": "source_conflict",
                        "content": "销售额来源不一致",
                        "source": "file",
                        "evidence_ids": [EVIDENCE_ID],
                        "blocking": True,
                    }
                ],
            },
        )
    revised = await preflight_harness.service.revise(
        "access-token",
        BRIEF_ID,
        BriefRevisionCommand(
            expected_revision=1,
            resolutions=(
                ConflictResolution(
                    code="source_conflict",
                    evidence_ids=(EVIDENCE_ID,),
                    action="choose_source",
                    selected_evidence_id=EVIDENCE_ID,
                ),
            ),
        ),
    )

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=revised.brief_id)
    )

    assert result.status == "preflight"
    assert result.has_blockers is False


@pytest.mark.asyncio
async def test_explicit_unit_resolution_clears_the_matching_evidence_blocker(
    preflight_harness,
) -> None:
    manifest = EvidenceManifest(
        schema_version="evidence-manifest.v1",
        manifest_id=f"m-{'5' * 64}",
        asset_id=ASSET_ID,
        asset_version=ASSET_VERSION,
        generated_at=datetime(2026, 7, 23, 23, 30, tzinfo=UTC),
        generator=EngineVersion(name="office-ai-evidence", version="1.0.0"),
        source_parser=EngineVersion(name="xlsx-safe", version="1.0.0"),
        evidence=(
            source_evidence().model_copy(
                update={
                    "unit": None,
                    "currency": None,
                    "calculation_blocked": True,
                    "warnings": ("numeric_unit_unknown",),
                }
            ),
        ),
    )
    stored = preflight_harness.manifest_store.write(USER_ID, ASSET_ID, manifest)
    async with preflight_harness.session_factory() as session, session.begin():
        asset = await session.get(FileAsset, ASSET_ID)
        asset.manifest_sha256 = stored.sha256
    revised = await preflight_harness.service.revise(
        "access-token",
        BRIEF_ID,
        BriefRevisionCommand(
            expected_revision=1,
            resolutions=(
                ConflictResolution(
                    code="unit_unknown",
                    evidence_ids=(EVIDENCE_ID,),
                    action="assign_unit",
                    value="CNY",
                ),
            ),
        ),
    )

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=revised.brief_id)
    )

    assert result.status == "preflight"
    assert result.has_blockers is False
    assert revised.source_snapshot["resolutions"] == [
        {
            "code": "unit_unknown",
            "evidence_ids": [EVIDENCE_ID],
            "action": "assign_unit",
            "value": "CNY",
            "selected_evidence_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_model_capability_change_is_an_incompatible_conflict(
    preflight_harness,
) -> None:
    async with preflight_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID)
        model.capabilities = {"text_generation": True, "structured_output": False}

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )

    assert result.status == "needs_resolution"
    assert [(item.code, item.level) for item in result.conflicts] == [
        ("model_capability_mismatch", "incompatible")
    ]


@pytest.mark.asyncio
async def test_model_snapshot_identity_change_is_incompatible(
    preflight_harness,
) -> None:
    async with preflight_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID)
        model.model_code = "agnes-drifted-model"

    result = await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )

    assert ("model_capability_mismatch", "incompatible") in [
        (item.code, item.level) for item in result.conflicts
    ]


@pytest.mark.asyncio
async def test_confirm_queues_the_clean_revision_and_is_idempotent(
    preflight_harness,
) -> None:
    await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )
    confirmed = await preflight_harness.service.confirm(
        "access-token", BRIEF_ID, accepted_estimated_credits=800
    )
    replay = await preflight_harness.service.confirm(
        "access-token", BRIEF_ID, accepted_estimated_credits=800
    )
    assert confirmed.status == "queued"
    assert confirmed.confirmed_at is not None
    assert replay == confirmed


@pytest.mark.asyncio
async def test_one_click_requires_a_clean_preflight_and_matching_acceptance(
    preflight_harness,
) -> None:
    result = await preflight_harness.service.preflight(
        "access-token",
        PreflightCommand(
            brief_id=BRIEF_ID,
            one_click=True,
            accepted_estimated_credits=800,
        ),
    )

    assert result.status == "queued"
    assert result.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirmation_detects_a_changed_estimate_before_queueing(
    preflight_harness,
) -> None:
    await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )
    async with preflight_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID)
        model.credit_multiplier = Decimal("1.1000")

    with pytest.raises(BriefOperationError) as error:
        await preflight_harness.service.confirm(
            "access-token", BRIEF_ID, accepted_estimated_credits=800
        )

    assert error.value.error_code == "estimated_credits_changed"
    async with preflight_harness.session_factory() as session:
        brief = await session.get(Brief, BRIEF_ID)
    assert brief.status == "preflight"
    assert brief.preflight_snapshot["estimated_credits"] == 880


@pytest.mark.asyncio
async def test_confirmation_persists_a_new_source_blocker_before_rejecting(
    preflight_harness,
) -> None:
    await preflight_harness.service.preflight(
        "access-token", PreflightCommand(brief_id=BRIEF_ID)
    )
    async with preflight_harness.session_factory() as session, session.begin():
        asset = await session.get(FileAsset, ASSET_ID)
        asset.processing_status = "rejected"

    with pytest.raises(BriefOperationError) as error:
        await preflight_harness.service.confirm(
            "access-token", BRIEF_ID, accepted_estimated_credits=800
        )

    assert error.value.error_code == "preflight_blocked"
    async with preflight_harness.session_factory() as session:
        brief = await session.get(Brief, BRIEF_ID)
    assert brief.status == "needs_resolution"
    assert brief.preflight_snapshot["has_blockers"] is True


@pytest.mark.asyncio
async def test_confirmed_estimate_is_not_recomputed_or_increased(
    preflight_harness,
) -> None:
    confirmed = await preflight_harness.service.preflight(
        "access-token",
        PreflightCommand(
            brief_id=BRIEF_ID,
            one_click=True,
            accepted_estimated_credits=800,
        ),
    )
    async with preflight_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID)
        model.credit_multiplier = Decimal("2.0000")

    replay = await preflight_harness.service.confirm(
        "access-token", BRIEF_ID, accepted_estimated_credits=800
    )

    assert confirmed.estimated_credits == 800
    assert replay.estimated_credits == 800
