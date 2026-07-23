from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models.credit_ledger import CreditLedger
from app.models.users import User
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
)
from app.services.quality.presentation.contracts import (
    LibreOfficeVerification,
    PresentationOutputReference,
    PresentationQualityFinding,
    PresentationQualityReport,
    PresentationValidatedOutputReference,
)
from app.services.quality.presentation.service import PresentationQualityOutcome
from tests.generation.conftest import (
    BRIEF_ID,
    USER_ID,
    generation_harness as _generation_harness,  # noqa: F401
)


class AllowAllCredentialLimiter:
    async def acquire(self, **_kwargs) -> bool:
        return True


def blocked_outcome() -> PresentationQualityOutcome:
    asset_id = UUID("019b0000-0000-7000-8000-000000000351")
    source = PresentationOutputReference(
        asset_id=asset_id,
        sha256="a" * 64,
        byte_size=1024,
        slide_count=3,
        renderer_version="ppt-renderer.v1",
        template_code="ppt.executive-blue.v1",
        template_version="1.0.0",
        plan_sha256="b" * 64,
    )
    report = PresentationQualityReport(
        schema_version="presentation-quality-report.v1",
        quality_engine_version="presentation-quality.v1",
        source=source,
        validated_output=PresentationValidatedOutputReference(
            asset_id=asset_id,
            sha256=source.sha256,
            byte_size=source.byte_size,
        ),
        status="blocked",
        download_allowed=False,
        findings=[
            PresentationQualityFinding(
                code="blank_slide",
                severity="blocker",
                rule_version="presentation-content.v1",
                slide_number=2,
                repairable=False,
            )
        ],
        libreoffice=LibreOfficeVerification(
            status="failed",
            error_code="quality_precheck_blocked",
        ),
        previews=[],
        repair_attempt_count=0,
        generated_at=datetime(2026, 7, 23, tzinfo=UTC),
    )
    return PresentationQualityOutcome(
        report=report,
        report_key="internal-report-key",
        report_sha256="c" * 64,
        validated_key=None,
        replayed=False,
    )


async def test_blocked_quality_fails_task_and_releases_full_reserve(
    _generation_harness,  # noqa: F811
) -> None:
    created = await _generation_harness.service.create(
        "access-token", BRIEF_ID, "quality-blocked"
    )
    processed = await GenerationWorkerService(
        _generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(
        created.task_id,
        ControlledStepExecutor([blocked_outcome().step_result()]),
    )

    async with _generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        entries = list(
            await session.scalars(
                select(CreditLedger).where(CreditLedger.task_id == created.task_id)
            )
        )

    assert processed.status == "failed"
    assert processed.error_category == "presentation_quality_blocked"
    assert user.credit_balance == 5_000
    assert [(entry.entry_type, entry.amount) for entry in entries] == [
        ("generation_reserve", -800),
        ("generation_release", 800),
    ]
