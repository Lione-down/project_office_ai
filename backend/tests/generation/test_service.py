from sqlalchemy import event, func, select

from app.models.credit_ledger import CreditLedger
from app.models.briefs import Brief
from app.models.generation_task_inputs import GenerationTaskInput
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent
from app.models.users import User
from app.models.ai_models import AiModel
from app.services.generation_contracts import GenerationOperationError
from app.templates.catalog import get_presentation_template
from tests.generation.conftest import BRIEF_ID, MODEL_ID, USER_ID


async def test_idempotent_creation_reserves_once_and_freezes_inputs(
    generation_harness,
) -> None:
    first = await generation_harness.service.create(
        "access-token", BRIEF_ID, "generation-request-001"
    )
    replay = await generation_harness.service.create(
        "access-token", BRIEF_ID, "generation-request-001"
    )

    async with generation_harness.session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(GenerationTask)) == 1
        )
        assert await session.scalar(select(func.count()).select_from(CreditLedger)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        assert (
            await session.scalar(select(func.count()).select_from(GenerationTaskStep))
            == 1
        )
        assert (
            await session.scalar(select(func.count()).select_from(GenerationTaskInput))
            == 3
        )
        user = await session.get(User, USER_ID)
        reserve = await session.scalar(select(CreditLedger))
        task = await session.scalar(select(GenerationTask))
        brief_input = await session.scalar(
            select(GenerationTaskInput).where(GenerationTaskInput.input_type == "brief")
        )

    assert first.task_id == replay.task_id
    assert replay.replayed is True
    assert first.status == "queued"
    assert first.estimated_credits == 800
    assert user.credit_balance == 4_200
    assert reserve.entry_type == "generation_reserve"
    assert reserve.amount == -800
    assert reserve.task_id == first.task_id
    assert task.skill_snapshot[0]["version"] == "1.0.0"
    assert (
        task.skill_snapshot[0]["template_checksum"]
        == get_presentation_template("ppt.executive-blue.v1").checksum
    )
    assert brief_input.snapshot["resolutions"] == [
        {
            "code": "unit_unknown",
            "evidence_ids": [f"e-{'1' * 64}"],
            "action": "assign_unit",
            "value": "CNY",
            "selected_evidence_id": None,
        }
    ]


async def test_creation_rejects_cross_owner_and_insufficient_credit(
    generation_harness,
) -> None:
    try:
        await generation_harness.service.create(
            "other-token", BRIEF_ID, "generation-request-other"
        )
    except GenerationOperationError as exception:
        assert exception.error_code == "brief_not_found"
    else:
        raise AssertionError("cross-owner Brief must not create a task")

    async with generation_harness.session_factory() as session, session.begin():
        user = await session.get(User, USER_ID, with_for_update=True)
        user.credit_balance = 799

    try:
        await generation_harness.service.create(
            "access-token", BRIEF_ID, "generation-request-insufficient"
        )
    except GenerationOperationError as exception:
        assert exception.error_code == "insufficient_credits"
    else:
        raise AssertionError("insufficient credit must fail")

    async with generation_harness.session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(GenerationTask)) == 0
        )
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 0


async def test_creation_requires_latest_confirmed_snapshot(
    generation_harness,
) -> None:
    async with generation_harness.session_factory() as session, session.begin():
        brief = await session.get(
            __import__("app.models.briefs", fromlist=["Brief"]).Brief,
            BRIEF_ID,
            with_for_update=True,
        )
        brief.status = "preflight"

    try:
        await generation_harness.service.create(
            "access-token", BRIEF_ID, "generation-request-unconfirmed"
        )
    except GenerationOperationError as exception:
        assert exception.error_code == "brief_not_confirmed"
    else:
        raise AssertionError("unconfirmed Brief must fail")


async def test_outbox_write_failure_rolls_back_task_reserve_and_balance(
    generation_harness,
) -> None:
    def fail_outbox_write(*_args):
        raise RuntimeError("simulated outbox failure")

    event.listen(OutboxEvent, "before_insert", fail_outbox_write)
    try:
        try:
            await generation_harness.service.create(
                "access-token", BRIEF_ID, "generation-outbox-rollback"
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("outbox failure must abort generation transaction")
    finally:
        event.remove(OutboxEvent, "before_insert", fail_outbox_write)

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        task_count = await session.scalar(
            select(func.count()).select_from(GenerationTask)
        )
        ledger_count = await session.scalar(
            select(func.count()).select_from(CreditLedger)
        )
    assert user.credit_balance == 5_000
    assert task_count == 0
    assert ledger_count == 0


async def test_service_rejects_invalid_idempotency_key_before_database_write(
    generation_harness,
) -> None:
    try:
        await generation_harness.service.create(
            "access-token", BRIEF_ID, " unsafe key "
        )
    except GenerationOperationError as exception:
        assert exception.error_code == "idempotency_key_invalid"
    else:
        raise AssertionError("service boundary must reject unsafe idempotency key")

    async with generation_harness.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(GenerationTask))
    assert count == 0


async def test_creation_rejects_model_or_credit_snapshot_drift(
    generation_harness,
) -> None:
    async with generation_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID, with_for_update=True)
        model.credit_multiplier = "1.2500"

    try:
        await generation_harness.service.create(
            "access-token", BRIEF_ID, "generation-stale-model"
        )
    except GenerationOperationError as exception:
        assert exception.error_code == "generation_preflight_stale"
    else:
        raise AssertionError("changed model pricing must require a new preflight")

    async with generation_harness.session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(GenerationTask))
    assert count == 0


async def test_creation_rejects_internally_inconsistent_output_credits(
    generation_harness,
) -> None:
    async with generation_harness.session_factory() as session, session.begin():
        brief = await session.get(Brief, BRIEF_ID, with_for_update=True)
        snapshot = dict(brief.preflight_snapshot)
        snapshot["outputs"] = [{**snapshot["outputs"][0], "estimated_credits": 799}]
        brief.preflight_snapshot = snapshot

    try:
        await generation_harness.service.create(
            "access-token", BRIEF_ID, "generation-credit-integrity"
        )
    except GenerationOperationError as exception:
        assert exception.error_code == "brief_integrity_failed"
    else:
        raise AssertionError("output fees must add up to the locked total")
