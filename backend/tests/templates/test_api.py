from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.settings.config import Settings


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class TemplateStub:
    async def list_published(self, access_token: str, *, category: str | None):
        assert access_token == "access-token"
        assert category == "management"
        return [
            {
                "template_code": "ppt.executive-blue.v1",
                "version": "1.0.0",
                "checksum": "a" * 64,
                "name": "高管钢蓝",
                "category": "management",
                "style_keywords": ["克制", "专业"],
                "use_cases": ["管理层汇报"],
                "cover_url": "/template-previews/ppt.executive-blue.v1/cover.svg",
                "representative_urls": [
                    "/template-previews/ppt.executive-blue.v1/content.svg"
                ],
                "compatible_skills": [
                    "ppt.sales-business-review.v1",
                    "ppt.knowledge-education.v1",
                ],
            }
        ]

    async def get_published(
        self,
        access_token: str,
        template_code: str,
        *,
        version: str | None,
    ):
        assert access_token == "access-token"
        assert template_code == "ppt.executive-blue.v1"
        assert version == "1.0.0"
        return {
            **(await self.list_published(access_token, category="management"))[0],
            "description": "原创管理汇报模板",
            "colors": ["#123B6D", "#29A3A3"],
            "fonts": ["Microsoft YaHei"],
            "layouts": ["title", "content", "section", "closing"],
            "compatible_skills": [
                "ppt.sales-business-review.v1",
                "ppt.knowledge-education.v1",
            ],
            "source": {
                "kind": "system_original",
                "license": "Office AI Original",
                "attribution": "Office AI Design System",
            },
        }


async def test_template_api_lists_and_reads_published_system_metadata() -> None:
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        template_services=TemplateStub(),
    )
    headers = {"Authorization": "Bearer access-token"}
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        listing = await client.get(
            "/api/v1/templates?category=management",
            headers=headers,
        )
        detail = await client.get(
            "/api/v1/templates/ppt.executive-blue.v1?version=1.0.0",
            headers=headers,
        )

    assert listing.status_code == 200
    assert detail.status_code == 200
    assert listing.headers["cache-control"] == "private, no-store"
    assert detail.headers["cache-control"] == "private, no-store"
    assert listing.json()[0]["checksum"] == "a" * 64
    assert detail.json()["source"]["kind"] == "system_original"
    assert detail.json()["compatible_skills"] == [
        "ppt.sales-business-review.v1",
        "ppt.knowledge-education.v1",
    ]
