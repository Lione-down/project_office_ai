import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

TRACE_ID_HEADER = "X-Trace-ID"
_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_request_logger = logging.getLogger("office_ai.request")


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming_trace_id = request.headers.get(TRACE_ID_HEADER, "")
        trace_id = (
            incoming_trace_id
            if _TRACE_ID_PATTERN.fullmatch(incoming_trace_id)
            else str(uuid4())
        )
        request.state.trace_id = trace_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id
        _request_logger.info(
            "request_completed",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        )
        return response
