from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from app.services.quality.presentation.contracts import (
    PresentationOutputReference,
    PresentationQualityFinding,
    PresentationQualityReport,
)


def source_reference(pending) -> PresentationOutputReference:
    return PresentationOutputReference(
        asset_id=pending.asset_id,
        sha256=pending.source_sha256,
        byte_size=pending.source_byte_size,
        slide_count=pending.slide_count,
        renderer_version=pending.renderer_version,
        template_code=pending.template_code,
        template_version=pending.template_version,
        plan_sha256=pending.plan_sha256,
    )


def ensure_report_matches(
    pending, plan, report: PresentationQualityReport, error_type
) -> None:
    if not (
        report.source == source_reference(pending)
        and report.validated_output.asset_id == pending.asset_id
        and report.quality_engine_version == "presentation-quality.v1"
        and plan.renderer_version == pending.renderer_version
    ):
        raise error_type("presentation_quality_report_invalid")


def validated_key(pending, report: PresentationQualityReport) -> str | None:
    if not report.download_allowed:
        return None
    if report.repair_attempt_count == 0:
        return pending.storage_key
    return f"users/{pending.user_id}/outputs/{pending.asset_id}/quality/repaired.pptx"


def request_id(asset_id: UUID, validated_sha256: str) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"office-ai:presentation-quality:{asset_id}:{validated_sha256}",
    )


def blocker(code: str, rule_version: str) -> PresentationQualityFinding:
    return PresentationQualityFinding(
        code=code,
        severity="blocker",
        rule_version=rule_version,
        repairable=False,
    )


def required(value):
    if value is None:
        raise ValueError("presentation_preview_invalid")
    return value


def file_digest(path: Path) -> tuple[str, int]:
    checksum = sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            checksum.update(chunk)
    return checksum.hexdigest(), size
