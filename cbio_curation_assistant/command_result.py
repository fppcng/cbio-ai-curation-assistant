"""Shared machine-readable response contract for agent-facing commands.

``success`` means the requested operation completed, including when existing
artifacts were safely reused. ``partial_success`` means useful artifacts were
produced but the operation did not fully complete; callers must inspect the
warnings and must not treat candidates as canonical outputs. ``error`` means
the operation failed and no successful result may be assumed.

After argument parsing, commands use this envelope on stdout. Their exit codes
are 0 for success, 1 for error, and 3 for partial success. Argument-parser
usage failures remain exit code 2 and retain argparse's standard diagnostics.
The bundled cBioPortal validator deliberately keeps its independent contract.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Literal, TypeAlias, TypeVar


CommandStatus: TypeAlias = Literal["success", "partial_success", "error"]
ResultT = TypeVar("ResultT")

SCHEMA_VERSION = 1
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_PARTIAL_SUCCESS = 3

_EXIT_CODES: dict[CommandStatus, int] = {
    "success": EXIT_SUCCESS,
    "partial_success": EXIT_PARTIAL_SUCCESS,
    "error": EXIT_ERROR,
}


@dataclass(frozen=True, slots=True)
class CommandErrorDetail:
    type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "message": self.message}


def _json_value(value: Any) -> Any:
    """Serialize supported domain values at an output boundary."""
    if hasattr(value, "to_dict"):
        return _json_value(value.to_dict())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class CommandResult(Generic[ResultT]):
    """Typed command response serialized only when emitted or persisted."""

    command: str
    status: CommandStatus
    result: ResultT | None = None
    warnings: tuple[str, ...] = ()
    error: CommandErrorDetail | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status == "error" and self.error is None:
            raise ValueError("An error response requires error details.")
        if self.status != "error" and self.error is not None:
            raise ValueError("Only an error response may contain error details.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "command": self.command,
            "status": self.status,
            "result": _json_value(self.result),
            "warnings": list(self.warnings),
            "error": self.error.to_dict() if self.error is not None else None,
        }


def error_detail(error: BaseException | str) -> CommandErrorDetail:
    """Convert an exception or message into the shared error representation."""
    if isinstance(error, BaseException):
        return CommandErrorDetail(type(error).__name__, str(error))
    return CommandErrorDetail("CommandError", str(error))


def command_result(
    command: str,
    *,
    status: CommandStatus,
    result: ResultT | None = None,
    warnings: Sequence[str] = (),
    error: Mapping[str, str] | BaseException | str | None = None,
) -> CommandResult[ResultT]:
    """Build one response using the common command envelope."""
    rendered_error: CommandErrorDetail | None
    if error is None:
        rendered_error = None
    elif isinstance(error, Mapping):
        rendered_error = CommandErrorDetail(
            type=str(error.get("type", "CommandError")),
            message=str(error.get("message", "")),
        )
    else:
        rendered_error = error_detail(error)

    return CommandResult(
        command=command,
        status=status,
        result=result,
        warnings=tuple(str(warning) for warning in warnings),
        error=rendered_error,
    )


def command_error(
    command: str,
    error: Mapping[str, str] | BaseException | str,
    *,
    result: Any = None,
    warnings: Sequence[str] = (),
) -> CommandResult[Any]:
    """Build an error response."""
    return command_result(
        command,
        status="error",
        result=result,
        warnings=warnings,
        error=error,
    )


def exit_code_for_status(status: CommandStatus) -> int:
    """Return the standardized process exit code for a command status."""
    return _EXIT_CODES[status]


def emit_command_result(payload: CommandResult[Any] | Mapping[str, Any]) -> None:
    """Print exactly one command response to stdout."""
    rendered = payload.to_dict() if isinstance(payload, CommandResult) else dict(payload)
    print(json.dumps(_json_value(rendered), indent=2, ensure_ascii=False))


__all__ = [
    "CommandStatus",
    "CommandErrorDetail",
    "CommandResult",
    "EXIT_ERROR",
    "EXIT_PARTIAL_SUCCESS",
    "EXIT_SUCCESS",
    "EXIT_USAGE",
    "SCHEMA_VERSION",
    "command_error",
    "command_result",
    "emit_command_result",
    "error_detail",
    "exit_code_for_status",
]
