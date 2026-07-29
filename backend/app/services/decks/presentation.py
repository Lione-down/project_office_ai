from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.services.decks.contracts import DeckBrief
from app.services.media.images.validation import (
    ImageAssetValidationError,
    image_data_uri,
    validate_image_bytes,
)
from app.services.renderers.presentation.contracts import PresentationPlan
from app.services.renderers.presentation.contracts import PresentationContractError


@dataclass(frozen=True)
class DeckImageBinding:
    asset_id: str
    asset_version: int
    data_uri: str
    mime_type: Literal["image/png", "image/jpeg"]
    byte_size: int
    sha256: str
    width: int
    height: int
    crop_mode: Literal["contain", "cover"]
    alt_text: str

    @classmethod
    def from_bytes(
        cls,
        *,
        asset_id: str,
        asset_version: int,
        data: bytes,
        alt_text: str,
        crop_mode: Literal["contain", "cover"],
        max_bytes: int,
        max_decoded_bytes: int,
        expected_sha256: str | None = None,
    ) -> "DeckImageBinding":
        try:
            image = validate_image_bytes(
                data,
                max_bytes=max_bytes,
                max_decoded_bytes=max_decoded_bytes,
            )
        except ImageAssetValidationError as exception:
            raise PresentationContractError(
                "presentation_image_integrity_invalid"
            ) from exception
        if expected_sha256 is not None and image.sha256 != expected_sha256:
            raise PresentationContractError("presentation_image_integrity_invalid")
        return cls(
            asset_id=asset_id,
            asset_version=asset_version,
            data_uri=image_data_uri(image),
            mime_type=image.mime_type,
            byte_size=image.byte_size,
            sha256=image.sha256,
            width=image.width,
            height=image.height,
            crop_mode=crop_mode,
            alt_text=alt_text,
        )


class DeckPresentationComposer:
    def compose(
        self,
        deck: DeckBrief,
        *,
        template_code: str,
        revision: int,
        images: dict[UUID, DeckImageBinding] | None = None,
    ) -> PresentationPlan:
        images = images or {}
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for slide in deck.slides
                for provenance in slide.provenance
                for evidence_id in provenance.evidence_ids
            )
        )
        slides = [
            self._slide(deck, index, len(deck.slides), images)
            for index in range(len(deck.slides))
        ]
        plan_images = {
            f"media-{slide_id}": {
                "asset_id": image.asset_id,
                "asset_version": image.asset_version,
                "data_uri": image.data_uri,
                "mime_type": image.mime_type,
                "byte_size": image.byte_size,
                "sha256": image.sha256,
                "width": image.width,
                "height": image.height,
                "crop_mode": image.crop_mode,
                "alt_text": image.alt_text,
            }
            for slide_id, image in images.items()
        }
        return PresentationPlan.validate_for_renderer(
            {
                "schema_version": "presentation-plan.v1",
                "renderer_version": "ppt-renderer.v1",
                "template": {"code": template_code, "version": "1.0.0"},
                "locale": deck.language,
                "metadata": {
                    "title": deck.topic[:500],
                    "subject": f"{deck.audience}｜{deck.style}"[:500],
                    "author": "Office AI",
                    "company": "Office AI",
                    "revision": str(revision),
                },
                "evidence_ids": evidence_ids,
                "images": plan_images,
                "data_sources": {},
                "slides": slides,
            }
        )

    @staticmethod
    def _slide(
        deck: DeckBrief,
        index: int,
        slide_count: int,
        images: dict[UUID, DeckImageBinding],
    ) -> dict:
        slide = deck.slides[index]
        image = images.get(slide.slide_id)
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for provenance in slide.provenance
                for evidence_id in provenance.evidence_ids
            )
        )
        notes = DeckPresentationComposer._notes(slide.speaker_notes)
        provenance_kinds = {item.kind for item in slide.provenance}
        if "agnes_inference" in provenance_kinds:
            notes.append("本页含 AI 生成且尚未核验的内容。")
        if evidence_ids:
            notes.append("Evidence: " + ", ".join(evidence_ids))
        layout = (
            "title"
            if index == 0
            else "closing"
            if index == slide_count - 1
            else "content"
        )
        elements = []
        for body_index, body in enumerate(slide.body):
            element = {
                "type": "text",
                "text": body,
                "x": 0.9,
                "y": 1.35 + 0.43 * body_index,
                "w": 7.35 if image is not None else 11.5,
                "h": 0.35,
            }
            if evidence_ids:
                element["evidence_ids"] = evidence_ids
            elements.append(element)
        if image is not None:
            elements.append(
                {
                    "type": "image",
                    "image_id": f"media-{slide.slide_id}",
                    "x": 8.65,
                    "y": 1.35,
                    "w": 3.75,
                    "h": 4.85,
                    "decorative": True,
                }
            )
        return {
            "layout": layout,
            "title": slide.title,
            "subtitle": slide.purpose if index == 0 else None,
            "speaker_notes": notes or ["用户已确认的 Deck Brief 页面。"],
            "elements": elements,
        }

    @staticmethod
    def _notes(value: str) -> list[str]:
        cleaned = value.strip()
        return [
            cleaned[offset : offset + 500] for offset in range(0, len(cleaned), 500)
        ][:18]
