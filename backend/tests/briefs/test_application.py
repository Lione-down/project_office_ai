from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.application import create_app
from app.settings.config import Settings


async def test_brief_generation_wiring_does_not_depend_on_provider_admin_factory() -> (
    None
):
    app = create_app(
        settings=Settings(
            explicit_database_url=SecretStr("sqlite+aiosqlite:///:memory:"),
            session_secret=SecretStr("s" * 32),
            master_key=SecretStr(Fernet.generate_key().decode("ascii")),
        ),
        provider_services=object(),
    )

    async with app.router.lifespan_context(app):
        assert app.state.brief_services.skills is not None
        assert app.state.brief_services.generation is not None
