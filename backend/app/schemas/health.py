from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["live", "ready"]
    trace_id: str
    dependencies: dict[str, Literal["up", "down"]] | None = None
