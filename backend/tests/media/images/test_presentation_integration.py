from io import BytesIO

from PIL import Image
import pytest

from app.services.decks.presentation import DeckImageBinding, DeckPresentationComposer
from app.services.decks.handoff import DeckHandoffService
from app.models.deck_draft_revisions import DeckDraftRevision
from app.models.deck_drafts import DeckDraft
from app.services.renderers.presentation.contracts import PresentationContractError

from .conftest import DRAFT_ID, REVISION_ID, SLIDE_IDS, deck
from .test_service_worker import command


def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 36), color=(24, 72, 120)).save(buffer, "PNG")
    return buffer.getvalue()


def test_deck_composer_binds_an_immutable_image_version_to_the_slide() -> None:
    plan = DeckPresentationComposer().compose(
        deck(),
        template_code="ppt.executive-blue.v1",
        revision=1,
        images={
            SLIDE_IDS[1]: DeckImageBinding.from_bytes(
                asset_id="019fad50-0000-7000-8000-000000000041",
                asset_version=1,
                data=image_bytes(),
                alt_text="季度趋势合成插画",
                crop_mode="cover",
                max_bytes=20 * 1024 * 1024,
                max_decoded_bytes=128 * 1024 * 1024,
            )
        },
    )

    image = plan.images[f"media-{SLIDE_IDS[1]}"]
    assert image.asset_id == "019fad50-0000-7000-8000-000000000041"
    assert image.asset_version == 1
    assert image.width == 64
    assert image.height == 36
    assert image.crop_mode == "cover"
    element = plan.slides[1].elements[-1]
    assert element.type == "image"
    assert element.image_id == f"media-{SLIDE_IDS[1]}"
    assert element.decorative is True


def test_deck_image_binding_rejects_claimed_asset_integrity_drift() -> None:
    with pytest.raises(PresentationContractError):
        DeckImageBinding.from_bytes(
            asset_id="019fad50-0000-7000-8000-000000000041",
            asset_version=1,
            data=image_bytes(),
            alt_text="季度趋势合成插画",
            crop_mode="cover",
            max_bytes=20 * 1024 * 1024,
            max_decoded_bytes=128 * 1024 * 1024,
            expected_sha256="0" * 64,
        )


async def test_deck_handoff_freezes_the_latest_ready_image_asset(
    image_harness,
) -> None:
    created = await image_harness.service.create(
        "access",
        DRAFT_ID,
        command(),
        "image-freeze-0001",
    )
    await image_harness.worker.process(created.media_job_id)

    async with image_harness.session_factory() as session:
        draft_row = await session.get(DeckDraft, DRAFT_ID)
        revision_row = await session.get(DeckDraftRevision, REVISION_ID)
        inputs = await DeckHandoffService._image_inputs(
            session,
            draft_row,
            revision_row,
        )

    assert len(inputs) == 1
    assert inputs[0]["reference_key"] == str(SLIDE_IDS[1])
    assert inputs[0]["snapshot"]["media_job_id"] == str(created.media_job_id)
    assert inputs[0]["snapshot"]["width"] == 64
    assert inputs[0]["snapshot"]["height"] == 36
