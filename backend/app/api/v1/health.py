from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse, response_model_exclude_none=True)
async def get_liveness(request: Request) -> HealthResponse:
    return HealthResponse(status="live", trace_id=request.state.trace_id)


@router.get("/ready", response_model=None)
async def get_readiness(request: Request) -> HealthResponse | JSONResponse:
    dependency_status = await request.app.state.readiness_checker.check()
    dependencies = {
        name: "up" if is_available else "down"
        for name, is_available in dependency_status.items()
    }
    trace_id = request.state.trace_id
    if all(dependency_status.values()):
        return HealthResponse(
            status="ready", trace_id=trace_id, dependencies=dependencies
        )

    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "error_code": "service_not_ready",
                "message": "服务依赖尚未就绪",
                "trace_id": trace_id,
            },
            "readiness": {
                "status": "not_ready",
                "dependencies": dependencies,
            },
        },
    )
