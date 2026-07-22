import asyncio

import pytest

from app.services.file_safety.clamav import ClamAVScanner
from app.services.file_safety.contracts import FileSafetyError


async def serve_once(response: bytes | None):
    received = bytearray()

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        received.extend(await reader.readuntil(b"\0"))
        while True:
            length = int.from_bytes(await reader.readexactly(4), "big")
            if length == 0:
                break
            received.extend(await reader.readexactly(length))
        if response is not None:
            writer.write(response)
            await writer.drain()
        else:
            await asyncio.sleep(0.1)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    return server, received


async def test_clean_clamav_response_is_accepted(tmp_path) -> None:
    path = tmp_path / "clean.txt"
    path.write_bytes(b"clean-content")
    server, received = await serve_once(b"stream: OK\0")
    port = server.sockets[0].getsockname()[1]

    async with server:
        result = await ClamAVScanner("127.0.0.1", port, timeout_seconds=1).scan(path)

    assert result.is_clean is True
    assert received.startswith(b"zINSTREAM\0")
    assert received.endswith(b"clean-content")


async def test_infected_clamav_response_is_rejected(tmp_path) -> None:
    path = tmp_path / "infected.txt"
    path.write_bytes(b"eicar")
    server, _ = await serve_once(b"stream: Eicar-Test-Signature FOUND\0")
    port = server.sockets[0].getsockname()[1]

    async with server:
        with pytest.raises(FileSafetyError) as captured:
            await ClamAVScanner("127.0.0.1", port, timeout_seconds=1).scan(path)

    assert captured.value.error_code == "virus_detected"
    assert "Eicar" not in captured.value.safe_message


@pytest.mark.parametrize("response", [b"stream: scan ERROR\0", b"unexpected\0"])
async def test_clamav_error_responses_fail_closed(tmp_path, response) -> None:
    path = tmp_path / "scan.txt"
    path.write_bytes(b"content")
    server, _ = await serve_once(response)
    port = server.sockets[0].getsockname()[1]

    async with server:
        with pytest.raises(FileSafetyError) as captured:
            await ClamAVScanner("127.0.0.1", port, timeout_seconds=1).scan(path)

    assert captured.value.error_code == "malware_scan_failed"


async def test_clamav_timeout_fails_closed(tmp_path) -> None:
    path = tmp_path / "timeout.txt"
    path.write_bytes(b"content")
    server, _ = await serve_once(None)
    port = server.sockets[0].getsockname()[1]

    async with server:
        with pytest.raises(FileSafetyError) as captured:
            await ClamAVScanner("127.0.0.1", port, timeout_seconds=0.01).scan(path)

    assert captured.value.error_code == "malware_scan_unavailable"


async def test_clamav_connection_failure_fails_closed(tmp_path) -> None:
    path = tmp_path / "unavailable.txt"
    path.write_bytes(b"content")

    with pytest.raises(FileSafetyError) as captured:
        await ClamAVScanner("127.0.0.1", 1, timeout_seconds=0.05).scan(path)

    assert captured.value.error_code == "malware_scan_unavailable"
