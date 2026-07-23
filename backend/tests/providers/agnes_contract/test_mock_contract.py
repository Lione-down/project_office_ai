import json

import httpx

from app.providers.agnes import AgnesAdapter, ChatCompletionRequest
from app.services.briefs.validation import validate_brief_response
from tests.briefs.helpers import valid_brief_payload
from tests.briefs.test_validation import expected_snapshot


async def test_mock_agnes_contract_returns_validated_structured_brief() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "agnes-contract-mock-1",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                valid_brief_payload(), ensure_ascii=False
                            )
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        completion = await AgnesAdapter(client=client).create_chat_completion(
            api_key="mock-key",
            request=ChatCompletionRequest(
                model="agnes-2.0-flash",
                messages=[
                    {
                        "role": "system",
                        "content": "Return the validated Structured Brief JSON.",
                    }
                ],
                tools=[],
                timeout_seconds=120,
                max_output_tokens=1024,
                temperature=0,
                trace_id="trace-agnes-contract-mock",
                response_format={"type": "json_object"},
            ),
        )

    brief = validate_brief_response(completion.content, expected_snapshot())
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert completion.provider_request_id == "agnes-contract-mock-1"
    assert completion.usage.total_tokens == 150
    assert brief.module == "ppt"


async def test_mock_agnes_contract_never_requires_local_image_url() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": "agnes-contract-mock-2",
                "choices": [
                    {
                        "message": {"content": '{"status":"ok"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await AgnesAdapter(client=client).create_chat_completion(
            api_key="mock-key",
            request=ChatCompletionRequest(
                model="agnes-2.0-flash",
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "evidence_id": f"e-{'1' * 64}",
                                "ocr_text": "销售额 12000 CNY",
                                "image_metadata": {
                                    "mime_type": "image/png",
                                    "width": 640,
                                    "height": 480,
                                },
                            }
                        ),
                    }
                ],
                tools=[],
                timeout_seconds=120,
                max_output_tokens=64,
                temperature=0,
                trace_id="trace-agnes-contract-image-metadata",
                response_format={"type": "json_object"},
            ),
        )

    assert "image_url" not in captured["body"]
    assert "localhost" not in captured["body"]
    assert "127.0.0.1" not in captured["body"]
    assert "storage_key" not in captured["body"]
