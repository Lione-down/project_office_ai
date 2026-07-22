import asyncio
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
import struct

from app.services.file_safety.contracts import FileSafetyError


@dataclass(frozen=True)
class ScanResult:
    is_clean: bool


class ClamAVScanner:
    def __init__(self, host: str, port: int, *, timeout_seconds: float) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds

    async def scan(self, path: Path) -> ScanResult:
        try:
            return await asyncio.wait_for(
                self._scan_stream(path), timeout=self._timeout_seconds
            )
        except FileSafetyError:
            raise
        except (TimeoutError, OSError, asyncio.IncompleteReadError) as exception:
            raise FileSafetyError(
                "malware_scan_unavailable", "病毒扫描服务不可用"
            ) from exception

    async def _scan_stream(self, path: Path) -> ScanResult:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        try:
            writer.write(b"zINSTREAM\0")
            with path.open("rb") as file_handle:
                while chunk := file_handle.read(1024 * 1024):
                    writer.write(struct.pack("!I", len(chunk)))
                    writer.write(chunk)
                    await writer.drain()
            writer.write(struct.pack("!I", 0))
            await writer.drain()
            response = (
                (await reader.readuntil(b"\0"))
                .rstrip(b"\0")
                .decode("utf-8", errors="replace")
            )
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
        if response.endswith(" OK"):
            return ScanResult(is_clean=True)
        if response.endswith(" FOUND"):
            raise FileSafetyError("virus_detected", "文件未通过病毒扫描")
        raise FileSafetyError("malware_scan_failed", "病毒扫描失败")
