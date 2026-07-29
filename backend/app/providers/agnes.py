from dataclasses import dataclass
import base64
import binascii
from ipaddress import ip_address
import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx


DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
DEFAULT_MODEL = "agnes-2.0-flash"
DEFAULT_CONTEXT_WINDOW = 262_144
DEFAULT_TIMEOUT_SECONDS = 120


class ProviderConfigurationError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class AgnesConfiguration:
    base_url: str
    model: str
    context_window: int
    timeout_seconds: int
    native_response_format: bool


@dataclass(frozen=True)
class ChatCompletionRequest:
    model: str
    messages: list[dict]
    tools: list[dict]
    timeout_seconds: int
    max_output_tokens: int
    temperature: float
    trace_id: str
    response_format: dict | None = None


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ChatStreamRequest:
    model: str
    messages: list[dict]
    tools: list[dict]
    timeout_seconds: int
    max_output_tokens: int
    trace_id: str
    thinking_enabled: bool
    stream: bool = True


@dataclass(frozen=True)
class ProviderStreamChunk:
    provider_request_id: str | None = None
    content_delta: str = ""
    finish_reason: str | None = None
    usage: ProviderUsage = ProviderUsage()


@dataclass(frozen=True)
class ProviderCompletion:
    provider_request_id: str | None
    content: str
    usage: ProviderUsage
    finish_reason: str | None
    status_summary: int


@dataclass(frozen=True)
class ImageGenerationRequest:
    model: str
    prompt: str
    size: str
    ratio: str
    input_images: tuple[str, ...]
    timeout_seconds: int
    trace_id: str


@dataclass(frozen=True)
class ProviderImage:
    provider_request_id: str | None
    image_bytes: bytes
    status_summary: int


@dataclass(frozen=True)
class VideoGenerationRequest:
    model: str
    prompt: str
    width: int
    height: int
    num_frames: int
    frame_rate: int
    negative_prompt: str | None
    timeout_seconds: int
    trace_id: str


@dataclass(frozen=True)
class ProviderVideo:
    provider_request_id: str | None
    video_id: str
    task_id: str | None
    status: str
    progress: int
    seconds: float | None
    width: int | None
    height: int | None
    result_url: str | None
    retry_after_seconds: int | None
    status_summary: int


@dataclass(frozen=True)
class ErrorClassification:
    category: str
    retryable: bool
    disable_credential: bool
    uncertain: bool


class AgnesAdapter:
    def __init__(
        self,
        *,
        configuration: dict | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.configuration = self.validate_configuration(configuration or {})
        self._client = client

    def validate_configuration(self, config: dict) -> AgnesConfiguration:
        base_url = str(config.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
        model = str(config.get("model", DEFAULT_MODEL)).strip()
        context_window = int(config.get("context_window", DEFAULT_CONTEXT_WINDOW))
        timeout_seconds = int(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        native_response_format = config.get("native_response_format", False)
        if urlparse(base_url).scheme != "https":
            raise ProviderConfigurationError(
                "provider_base_url_invalid", "Agnes Base URL 必须使用 HTTPS"
            )
        if not model:
            raise ProviderConfigurationError(
                "provider_model_invalid", "Agnes 模型代码不能为空"
            )
        if context_window < 1 or context_window > DEFAULT_CONTEXT_WINDOW:
            raise ProviderConfigurationError(
                "provider_context_invalid", "Agnes Context 必须在保守 256K 范围内"
            )
        if timeout_seconds < 1:
            raise ProviderConfigurationError(
                "provider_timeout_invalid", "Agnes timeout 必须大于 0"
            )
        if not isinstance(native_response_format, bool):
            raise ProviderConfigurationError(
                "provider_capability_invalid",
                "Agnes native_response_format 必须是布尔值",
            )
        return AgnesConfiguration(
            base_url=base_url,
            model=model,
            context_window=context_window,
            timeout_seconds=timeout_seconds,
            native_response_format=native_response_format,
        )

    async def test_authentication(self, api_key: str) -> bool:
        await self.create_chat_completion(
            api_key=api_key,
            request=ChatCompletionRequest(
                model=self.configuration.model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                tools=[],
                timeout_seconds=self.configuration.timeout_seconds,
                max_output_tokens=8,
                temperature=0,
                trace_id="credential-auth-test",
            ),
        )
        return True

    async def test_structured_output(self, api_key: str) -> bool:
        await self.create_chat_completion(
            api_key=api_key,
            request=ChatCompletionRequest(
                model=self.configuration.model,
                messages=[
                    {
                        "role": "user",
                        "content": 'Return JSON with one field: {"status":"ok"}.',
                    }
                ],
                tools=[],
                timeout_seconds=self.configuration.timeout_seconds,
                max_output_tokens=64,
                temperature=0,
                trace_id="credential-structured-output-test",
                response_format={"type": "json_object"},
            ),
        )
        return True

    async def test_image_url(self, api_key: str, image_url: str) -> bool:
        self._validate_public_image_url(image_url)
        await self.create_chat_completion(
            api_key=api_key,
            request=ChatCompletionRequest(
                model=self.configuration.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image briefly."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                tools=[],
                timeout_seconds=self.configuration.timeout_seconds,
                max_output_tokens=64,
                temperature=0,
                trace_id="credential-image-url-test",
            ),
        )
        return True

    async def create_chat_completion(
        self, *, api_key: str, request: ChatCompletionRequest
    ) -> ProviderCompletion:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        if request.tools:
            payload["tools"] = request.tools
        if (
            request.response_format is not None
            and self.configuration.native_response_format
        ):
            payload["response_format"] = request.response_format
        response = await self._post(
            "/chat/completions",
            api_key=api_key,
            trace_id=request.trace_id,
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exception:
            raise ProviderConfigurationError(
                "provider_response_invalid", "Agnes 响应合同无效"
            ) from exception
        return ProviderCompletion(
            provider_request_id=body.get("id"),
            content=content,
            usage=self.extract_usage(body),
            finish_reason=choice.get("finish_reason"),
            status_summary=response.status_code,
        )

    async def stream_chat_completion(
        self,
        *,
        api_key: str,
        request: ChatStreamRequest,
    ) -> AsyncIterator[ProviderStreamChunk]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_output_tokens,
            "temperature": 0.7,
            "stream": True,
        }
        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"
        if request.thinking_enabled:
            payload["chat_template_kwargs"] = {"enable_thinking": True}
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Trace-ID": request.trace_id,
        }
        url = f"{self.configuration.base_url}/chat/completions"
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            async with client.stream(
                "POST",
                url,
                content=json.dumps(payload, separators=(",", ":")),
                headers=headers,
                timeout=request.timeout_seconds,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        body = json.loads(data)
                    except json.JSONDecodeError as exception:
                        raise ProviderConfigurationError(
                            "provider_response_invalid",
                            "Agnes 流式响应合同无效",
                        ) from exception
                    choices = body.get("choices") or []
                    choice = choices[0] if choices else {}
                    delta = choice.get("delta") or {}
                    if delta.get("tool_calls"):
                        raise ProviderConfigurationError(
                            "chat_tool_not_enabled",
                            "当前会话未启用工具执行",
                        )
                    content = delta.get("content") or ""
                    if not isinstance(content, str):
                        raise ProviderConfigurationError(
                            "provider_response_invalid",
                            "Agnes 流式正文合同无效",
                        )
                    yield ProviderStreamChunk(
                        provider_request_id=body.get("id"),
                        content_delta=content,
                        finish_reason=choice.get("finish_reason"),
                        usage=self.extract_usage(body),
                    )
        finally:
            if owns_client:
                await client.aclose()

    async def create_image(
        self,
        *,
        api_key: str,
        request: ImageGenerationRequest,
    ) -> ProviderImage:
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "size": request.size,
            "ratio": request.ratio,
        }
        if request.input_images:
            payload["extra_body"] = {
                "image": list(request.input_images),
                "response_format": "b64_json",
            }
        else:
            payload["return_base64"] = True
        response = await self._post(
            "/images/generations",
            api_key=api_key,
            trace_id=request.trace_id,
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )
        response.raise_for_status()
        try:
            body = response.json()
            items = body["data"]
            encoded = items[0]["b64_json"]
            if (
                not isinstance(items, list)
                or len(items) != 1
                or not isinstance(encoded, str)
                or not encoded
            ):
                raise ValueError("invalid image response")
            image_bytes = base64.b64decode(encoded, validate=True)
            if not image_bytes:
                raise ValueError("empty image response")
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            binascii.Error,
            json.JSONDecodeError,
        ) as exception:
            raise ProviderConfigurationError(
                "provider_response_invalid",
                "Agnes 图片响应合同无效",
            ) from exception
        provider_request_id = body.get("id")
        if not isinstance(provider_request_id, str) or not provider_request_id:
            provider_request_id = response.headers.get("x-request-id")
        return ProviderImage(
            provider_request_id=provider_request_id,
            image_bytes=image_bytes,
            status_summary=response.status_code,
        )

    async def create_video(
        self,
        *,
        api_key: str,
        request: VideoGenerationRequest,
    ) -> ProviderVideo:
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "width": request.width,
            "height": request.height,
            "num_frames": request.num_frames,
            "frame_rate": request.frame_rate,
        }
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        response = await self._post(
            "/videos",
            api_key=api_key,
            trace_id=request.trace_id,
            payload=payload,
            timeout_seconds=request.timeout_seconds,
        )
        response.raise_for_status()
        return self._extract_video(response)

    async def get_video(
        self,
        *,
        api_key: str,
        model: str,
        video_id: str,
        timeout_seconds: int,
        trace_id: str,
    ) -> ProviderVideo:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Trace-ID": trace_id,
        }
        base_url = self.configuration.base_url
        gateway_url = (
            f"{base_url[:-3]}/agnesapi"
            if base_url.endswith("/v1")
            else f"{base_url}/agnesapi"
        )
        params = {"video_id": video_id, "model_name": model}
        if self._client is not None:
            response = await self._client.get(
                gateway_url,
                params=params,
                headers=headers,
                timeout=timeout_seconds,
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    gateway_url,
                    params=params,
                    headers=headers,
                    timeout=timeout_seconds,
                )
        response.raise_for_status()
        return self._extract_video(response)

    @staticmethod
    def _extract_video(response: httpx.Response) -> ProviderVideo:
        try:
            body = response.json()
            status = body["status"]
            video_id = body["video_id"]
            if status not in {"queued", "in_progress", "completed", "failed"}:
                raise ValueError("unknown video status")
            if not isinstance(video_id, str) or not video_id:
                raise ValueError("missing video id")
            task_id = body.get("task_id") or body.get("id")
            if task_id is not None and (not isinstance(task_id, str) or not task_id):
                raise ValueError("invalid task id")
            progress = int(body.get("progress", 0))
            if progress < 0 or progress > 100:
                raise ValueError("invalid progress")
            seconds = (
                float(body["seconds"]) if body.get("seconds") is not None else None
            )
            size = body.get("size")
            width = height = None
            if size is not None:
                if not isinstance(size, str) or "x" not in size:
                    raise ValueError("invalid video size")
                raw_width, raw_height = size.lower().split("x", 1)
                width, height = int(raw_width), int(raw_height)
                if width < 1 or height < 1:
                    raise ValueError("invalid video size")
            metadata = body.get("metadata") or {}
            if not isinstance(metadata, dict):
                raise ValueError("invalid video metadata")
            result_url = metadata.get("url")
            if status == "completed":
                parsed_result = (
                    urlparse(result_url) if isinstance(result_url, str) else None
                )
                if (
                    parsed_result is None
                    or parsed_result.scheme != "https"
                    or not parsed_result.hostname
                ):
                    raise ValueError("missing video result")
            elif result_url is not None:
                raise ValueError("premature video result")
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exception:
            raise ProviderConfigurationError(
                "provider_response_invalid",
                "Agnes 视频响应合同无效",
            ) from exception
        provider_request_id = response.headers.get("x-request-id")
        retry_after = response.headers.get("retry-after")
        return ProviderVideo(
            provider_request_id=provider_request_id,
            video_id=video_id,
            task_id=task_id,
            status=status,
            progress=progress,
            seconds=seconds,
            width=width,
            height=height,
            result_url=result_url,
            retry_after_seconds=(
                min(int(retry_after), 3600)
                if retry_after is not None and retry_after.isdigit()
                else None
            ),
            status_summary=response.status_code,
        )

    def classify_error(self, error: Exception) -> ErrorClassification:
        if isinstance(error, httpx.TimeoutException):
            return ErrorClassification("provider_uncertain", False, False, True)
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code == 400:
                return ErrorClassification("invalid_request", False, False, False)
            if status_code in (401, 403):
                return ErrorClassification("authentication", False, True, False)
            if status_code == 429:
                return ErrorClassification("rate_limited", True, False, False)
            if status_code >= 500:
                return ErrorClassification("provider_error", True, False, False)
        return ErrorClassification("provider_error", False, False, False)

    def extract_usage(self, payload: dict) -> ProviderUsage:
        usage = payload.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        return ProviderUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=int(
                usage.get("total_tokens", prompt_tokens + completion_tokens)
            ),
        )

    async def _post(
        self,
        path: str,
        *,
        api_key: str,
        trace_id: str,
        payload: dict,
        timeout_seconds: int,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Trace-ID": trace_id,
        }
        url = f"{self.configuration.base_url}{path}"
        if self._client is not None:
            return await self._client.post(
                url,
                content=json.dumps(payload, separators=(",", ":")),
                headers=headers,
                timeout=timeout_seconds,
            )
        async with httpx.AsyncClient() as client:
            return await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )

    @staticmethod
    def _validate_public_image_url(image_url: str) -> None:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ProviderConfigurationError(
                "image_url_not_public", "图片 URL 必须是公网 HTTPS 地址"
            )
        if parsed.hostname.lower() == "localhost":
            raise ProviderConfigurationError(
                "image_url_not_public", "图片 URL 不能指向本机或私网"
            )
        try:
            address = ip_address(parsed.hostname)
        except ValueError:
            return
        if not address.is_global:
            raise ProviderConfigurationError(
                "image_url_not_public", "图片 URL 不能指向本机或私网"
            )
