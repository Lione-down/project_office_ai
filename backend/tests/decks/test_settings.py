from pathlib import Path

import yaml

from app.settings.config import Settings


ROOT = Path(__file__).resolve().parents[3]


def test_deck_limits_are_bounded_and_exposed_to_the_api_runtime() -> None:
    defaults = Settings()
    configured = Settings(
        OFFICE_AI_DECK_MAX_SLIDES=24,
        OFFICE_AI_DECK_MAX_CONTEXT_ASSETS=8,
    )
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert defaults.deck_max_slides == 40
    assert defaults.deck_max_context_assets == 20
    assert configured.deck_max_slides == 24
    assert configured.deck_max_context_assets == 8
    assert (
        compose["services"]["backend"]["environment"]["OFFICE_AI_DECK_MAX_SLIDES"]
        == "${OFFICE_AI_DECK_MAX_SLIDES:-40}"
    )
    assert (
        compose["services"]["backend"]["environment"][
            "OFFICE_AI_DECK_MAX_CONTEXT_ASSETS"
        ]
        == "${OFFICE_AI_DECK_MAX_CONTEXT_ASSETS:-20}"
    )
