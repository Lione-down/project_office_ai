import json
from copy import deepcopy
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from app.models import (
    AiModel,
    Brief,
    ProviderCall,
    ProviderCredential,
    TermItem,
    TermLibrary,
)
from app.providers.agnes import ProviderCompletion, ProviderUsage
from app.services.briefs.contracts import (
    BriefGenerationCommand,
    TermLibraryVersion,
)
from app.services.briefs.service import BriefOperationError
from app.services.preflight.catalog import PPT_DEFAULT_TEMPLATE
from app.services.auth_sessions import CurrentUser
from tests.briefs.helpers import (
    ASSET_ID,
    CREDENTIAL_ID,
    EVIDENCE_ID,
    MODEL_ID,
    PROJECT_ID,
    USER_ID,
    valid_brief_payload,
)


TERM_LIBRARY_ID = UUID("019f4000-0000-7000-8000-000000000030")


def command() -> BriefGenerationCommand:
    return BriefGenerationCommand(
        project_id=PROJECT_ID,
        asset_ids=(ASSET_ID,),
        term_library_versions=(),
        skill_codes=("ppt.sales-business-review.v1",),
        model_id=MODEL_ID,
        goal="形成月度销售经营复盘",
        audience="销售管理层",
        must_include=("销售额",),
        must_exclude=(),
    )


def completion(payload: dict, request_id: str) -> ProviderCompletion:
    provider_payload = deepcopy(payload)
    output_plan = provider_payload.get("output_plan")
    item_groups = [
        *(output_plan.get("deliverables", []) if isinstance(output_plan, dict) else []),
        *provider_payload.get("facts", []),
        *provider_payload.get("inferences", []),
        *provider_payload.get("unresolved_items", []),
        *provider_payload.get("must_include", []),
        *provider_payload.get("must_exclude", []),
    ]
    for item in item_groups:
        if isinstance(item, dict) and isinstance(item.get("evidence_ids"), list):
            item["evidence_ids"] = [
                "r0" if evidence_id == EVIDENCE_ID else evidence_id
                for evidence_id in item["evidence_ids"]
            ]
    return ProviderCompletion(
        provider_request_id=request_id,
        content=json.dumps(provider_payload, ensure_ascii=False),
        usage=ProviderUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
        finish_reason="stop",
        status_summary=200,
    )


async def test_generation_can_run_for_durable_worker_identity(brief_harness) -> None:
    brief_harness.adapter.outcomes = [
        completion(valid_brief_payload(), "agnes-worker-request")
    ]
    current_user = CurrentUser(
        user_id=USER_ID,
        phone_country_code="+86",
        phone_number="13800000000",
        role="user",
        status="active",
        credit_balance=0,
        must_change_password=False,
    )

    result = await brief_harness.service.generate_for_user(
        current_user,
        command(),
        trace_id="workflow-task:test",
    )

    assert result.brief_group_id is not None


async def test_generation_persists_immutable_brief_and_redacted_call_metadata(
    brief_harness,
) -> None:
    brief_harness.adapter.outcomes = [
        completion(valid_brief_payload(), "agnes-request-1")
    ]

    result = await brief_harness.service.generate(
        "access-token", command(), trace_id="trace-brief-1"
    )

    assert result.revision == 1
    assert result.status == "draft"
    assert result.content.facts[0].evidence_ids == (EVIDENCE_ID,)
    async with brief_harness.session_factory() as session:
        briefs = list(await session.scalars(select(Brief)))
        calls = list(await session.scalars(select(ProviderCall)))
    assert len(briefs) == 1
    assert briefs[0].content_checksum == result.content_checksum
    assert briefs[0].content == result.content.model_dump(mode="json")
    assert briefs[0].source_snapshot["goal"] == "形成月度销售经营复盘"
    assert briefs[0].source_snapshot["audience"] == "销售管理层"
    assert briefs[0].source_snapshot["must_include"] == [
        {
            "content": "销售额",
            "source": "user",
            "evidence_ids": [],
        }
    ]
    assert briefs[0].source_snapshot["template_versions"] == [
        {
            "template_code": PPT_DEFAULT_TEMPLATE,
            "version": "1.0.0",
        }
    ]
    assert len(calls) == 1
    assert calls[0].status == "succeeded"
    assert calls[0].provider_request_id == "agnes-request-1"
    assert calls[0].total_tokens == 150
    assert calls[0].is_redacted is True
    assert calls[0].brief_revision_id == briefs[0].id
    assert brief_harness.adapter.calls[0][0] == "mock-key"
    request = brief_harness.adapter.calls[0][1]
    serialized_messages = json.dumps(request.messages, ensure_ascii=False)
    assert "evidence_id" in serialized_messages
    assert EVIDENCE_ID not in serialized_messages
    assert "local_path" not in serialized_messages
    assert "mock-key" not in serialized_messages


async def test_generation_resolves_provider_evidence_aliases_before_persisting(
    brief_harness,
) -> None:
    payload = valid_brief_payload()
    payload["facts"][0]["evidence_ids"] = ["r0"]
    payload["inferences"][0]["evidence_ids"] = ["r0"]
    brief_harness.adapter.outcomes = [
        completion(payload, "agnes-request-evidence-alias")
    ]

    result = await brief_harness.service.generate(
        "access-token", command(), trace_id="trace-evidence-alias"
    )

    assert result.content.facts[0].evidence_ids == (EVIDENCE_ID,)
    assert result.content.inferences[0].evidence_ids == (EVIDENCE_ID,)
    async with brief_harness.session_factory() as session:
        brief = await session.scalar(select(Brief))
    assert brief.content["facts"][0]["evidence_ids"] == [EVIDENCE_ID]


async def test_invalid_schema_is_repaired_exactly_once(brief_harness) -> None:
    brief_harness.adapter.outcomes = [
        completion({"invalid": True}, "agnes-request-invalid"),
        completion(valid_brief_payload(), "agnes-request-repaired"),
    ]

    result = await brief_harness.service.generate(
        "access-token", command(), trace_id="trace-repair"
    )

    assert result.revision == 1
    assert len(brief_harness.adapter.calls) == 2
    async with brief_harness.session_factory() as session:
        calls = list(
            await session.scalars(select(ProviderCall).order_by(ProviderCall.attempt))
        )
    assert [call.status for call in calls] == ["schema_invalid", "succeeded"]
    assert [call.attempt for call in calls] == [1, 2]


async def test_second_invalid_schema_fails_without_persisting_brief(
    brief_harness,
) -> None:
    brief_harness.adapter.outcomes = [
        completion({"invalid": True}, "agnes-request-invalid-1"),
        completion({"still": "invalid"}, "agnes-request-invalid-2"),
    ]

    with pytest.raises(BriefOperationError) as error:
        await brief_harness.service.generate(
            "access-token", command(), trace_id="trace-double-invalid"
        )

    assert error.value.error_code == "brief_schema_invalid"
    assert len(brief_harness.adapter.calls) == 2
    async with brief_harness.session_factory() as session:
        assert list(await session.scalars(select(Brief))) == []
        calls = list(
            await session.scalars(select(ProviderCall).order_by(ProviderCall.attempt))
        )
    assert [call.status for call in calls] == [
        "schema_invalid",
        "schema_invalid",
    ]


async def test_fabricated_evidence_is_rejected_after_single_repair(
    brief_harness,
) -> None:
    fabricated = valid_brief_payload()
    fabricated["facts"][0]["evidence_ids"] = [f"e-{'f' * 64}"]
    brief_harness.adapter.outcomes = [
        completion(fabricated, "agnes-request-forged-1"),
        completion(fabricated, "agnes-request-forged-2"),
    ]

    with pytest.raises(BriefOperationError) as error:
        await brief_harness.service.generate(
            "access-token", command(), trace_id="trace-forged"
        )

    assert error.value.error_code == "brief_evidence_invalid"
    async with brief_harness.session_factory() as session:
        assert list(await session.scalars(select(Brief))) == []


async def test_context_overflow_fails_before_provider_call(brief_harness) -> None:
    async with brief_harness.session_factory() as session, session.begin():
        model = await session.get(AiModel, MODEL_ID)
        model.context_window = 700

    with pytest.raises(BriefOperationError) as error:
        await brief_harness.service.generate(
            "access-token", command(), trace_id="trace-context"
        )

    assert error.value.error_code == "context_budget_exceeded"
    assert brief_harness.adapter.calls == []
    async with brief_harness.session_factory() as session:
        assert list(await session.scalars(select(ProviderCall))) == []


async def test_timeout_is_persisted_as_uncertain_without_retry(
    brief_harness,
) -> None:
    brief_harness.adapter.outcomes = [
        httpx.ReadTimeout(
            "timeout",
            request=httpx.Request("POST", "https://apihub.agnes-ai.com/v1"),
        )
    ]

    with pytest.raises(BriefOperationError) as error:
        await brief_harness.service.generate(
            "access-token", command(), trace_id="trace-timeout"
        )

    assert error.value.error_code == "provider_uncertain"
    assert len(brief_harness.adapter.calls) == 1
    async with brief_harness.session_factory() as session:
        call = await session.scalar(select(ProviderCall))
        assert call.status == "provider_uncertain"
        assert call.error_category == "provider_uncertain"
        assert list(await session.scalars(select(Brief))) == []


async def test_authentication_error_pauses_selected_credential_without_fallback(
    brief_harness,
) -> None:
    response = httpx.Response(
        401,
        request=httpx.Request("POST", "https://apihub.agnes-ai.com/v1"),
    )
    brief_harness.adapter.outcomes = [
        httpx.HTTPStatusError(
            "unauthorized", request=response.request, response=response
        )
    ]

    with pytest.raises(BriefOperationError) as error:
        await brief_harness.service.generate(
            "access-token", command(), trace_id="trace-auth"
        )

    assert error.value.error_code == "authentication"
    assert len(brief_harness.adapter.calls) == 1
    async with brief_harness.session_factory() as session:
        credential = await session.get(ProviderCredential, CREDENTIAL_ID)
    assert credential.status == "paused"


async def test_selected_term_version_rules_are_included_in_provider_context(
    brief_harness,
) -> None:
    async with brief_harness.session_factory() as session, session.begin():
        library = TermLibrary(
            library_id=TERM_LIBRARY_ID,
            user_id=USER_ID,
            project_id=PROJECT_ID,
            previous_version_id=None,
            name="销售口径",
            description="销售项目术语",
            status="active",
            version=1,
        )
        session.add(library)
        await session.flush()
        session.add(
            TermItem(
                item_id=UUID("019f4000-0000-7000-8000-000000000031"),
                term_library_version_id=library.id,
                canonical_term="销售额",
                aliases=["营业收入"],
                unit="CNY",
                definition="已确认销售收入",
                metric_scope="含税销售额",
                priority=10,
            )
        )
    selected_command = command().model_copy(
        update={
            "term_library_versions": (
                TermLibraryVersion(library_id=TERM_LIBRARY_ID, version=1),
            )
        }
    )
    payload = valid_brief_payload()
    payload["term_library_versions"] = [
        {"library_id": str(TERM_LIBRARY_ID), "version": 1}
    ]
    brief_harness.adapter.outcomes = [completion(payload, "agnes-request-with-terms")]

    await brief_harness.service.generate(
        "access-token", selected_command, trace_id="trace-terms"
    )

    serialized_messages = json.dumps(
        brief_harness.adapter.calls[0][1].messages,
        ensure_ascii=False,
    )
    assert "销售额" in serialized_messages
    assert "营业收入" in serialized_messages
    assert "含税销售额" in serialized_messages
