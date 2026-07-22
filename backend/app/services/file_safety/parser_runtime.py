import multiprocessing
from multiprocessing.connection import Connection

from app.services.file_safety.contracts import FileDescriptor, FileSafetyError
from app.services.file_safety.parsers import ParsedDocument


def parse_in_subprocess(
    parser,
    descriptor: FileDescriptor,
    *,
    timeout_seconds: float,
) -> ParsedDocument:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_parse_child,
        args=(sender, parser, descriptor),
        name="office-ai-safe-parser",
        daemon=True,
    )
    try:
        process.start()
    except Exception as exception:
        receiver.close()
        sender.close()
        raise FileSafetyError("parser_process_failed", "文件解析失败") from exception
    sender.close()
    try:
        if not receiver.poll(timeout_seconds):
            _terminate(process)
            raise FileSafetyError("parser_timeout", "文件解析超时")
        try:
            status, payload = receiver.recv()
        except EOFError as exception:
            raise FileSafetyError(
                "parser_process_failed", "文件解析失败"
            ) from exception
    finally:
        receiver.close()
        if process.is_alive():
            process.join(timeout=0.2)
        if process.is_alive():
            _terminate(process)
    if status == "ok":
        return ParsedDocument(
            schema_version=payload["schema_version"],
            parser_name=payload["parser_name"],
            parser_version=payload["parser_version"],
            kind=payload["kind"],
            content=payload["content"],
            warnings=tuple(payload["warnings"]),
        )
    if status == "unsafe":
        raise FileSafetyError(payload["error_code"], payload["safe_message"])
    raise RuntimeError("parser subprocess failed")


def _parse_child(sender: Connection, parser, descriptor: FileDescriptor) -> None:
    try:
        document = parser.parse(descriptor)
        sender.send(("ok", document.to_dict()))
    except FileSafetyError as exception:
        sender.send(
            (
                "unsafe",
                {
                    "error_code": exception.error_code,
                    "safe_message": exception.safe_message,
                },
            )
        )
    except BaseException:
        sender.send(("failed", None))
    finally:
        sender.close()


def _terminate(process: multiprocessing.Process) -> None:
    if process.is_alive():
        process.terminate()
        process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)
