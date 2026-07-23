from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_assets import FileAsset
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.services.generation_contracts import (
    GenerationOperationError,
    GenerationOutputSnapshot,
    GenerationStepSnapshot,
)


def generation_step_snapshot(step: GenerationTaskStep) -> GenerationStepSnapshot:
    checkpoint = dict(step.checkpoint or {})
    return GenerationStepSnapshot(
        step_key=step.step_key,
        output_kind=step.output_kind,
        status=step.status,
        attempt=step.attempt,
        estimated_credits=step.estimated_credits,
        error_category=step.error_category,
        output_asset_id=_checkpoint_asset_id(checkpoint),
        asset_version=checkpoint.get("asset_version"),
        quality_status=checkpoint.get("quality_status"),
        download_allowed=checkpoint.get("quality_download_allowed", False),
        quality_report_schema_version=checkpoint.get("quality_report_schema_version"),
    )


def generation_output_snapshot(
    step: GenerationStepSnapshot,
) -> GenerationOutputSnapshot:
    return GenerationOutputSnapshot(
        output_kind=step.output_kind,
        status=step.status,
        estimated_credits=step.estimated_credits,
        error_category=step.error_category,
        asset_id=step.output_asset_id,
        asset_version=step.asset_version,
        quality_status=step.quality_status,
        download_allowed=step.download_allowed,
        quality_report_schema_version=step.quality_report_schema_version,
    )


async def verify_generation_output(
    session: AsyncSession,
    task: GenerationTask,
    step: GenerationStepSnapshot,
) -> None:
    if step.output_asset_id is None:
        if step.asset_version is not None or step.download_allowed:
            raise _integrity_error()
        return
    asset = await session.get(FileAsset, step.output_asset_id)
    expected_category = {"pptx": "presentation", "xlsx": "spreadsheet"}.get(
        step.output_kind
    )
    if (
        asset is None
        or asset.user_id != task.user_id
        or asset.generated_task_id != task.id
        or asset.file_category != expected_category
    ):
        raise _integrity_error()
    if step.quality_status is None:
        if (
            step.asset_version is not None
            or step.quality_report_schema_version is not None
            or step.download_allowed
            or asset.quality_status is not None
        ):
            raise _integrity_error()
        return
    is_downloadable = (
        asset.quality_status in {"passed", "passed_with_warnings"}
        and asset.quality_validated_key is not None
        and asset.quality_validated_sha256 is not None
        and asset.quality_validated_byte_size is not None
    )
    if (
        step.asset_version != f"sha256:{asset.sha256}"
        or step.quality_status != asset.quality_status
        or step.quality_report_schema_version != asset.quality_report_schema_version
        or step.download_allowed != is_downloadable
    ):
        raise _integrity_error()


def _checkpoint_asset_id(checkpoint: dict) -> UUID | None:
    value = checkpoint.get("output_asset_id")
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _integrity_error() -> GenerationOperationError:
    return GenerationOperationError(
        "generation_output_integrity_failed",
        "生成输出完整性校验失败",
        409,
    )
