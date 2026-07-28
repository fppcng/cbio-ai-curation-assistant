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
from typing import Any, Literal, TypeAlias


CommandStatus: TypeAlias = Literal["success", "partial_success", "error"]

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


def error_detail(error: BaseException | str) -> dict[str, str]:
    """Convert an exception or message into the shared error representation."""
    if isinstance(error, BaseException):
        return {
            "type": type(error).__name__,
            "message": str(error),
        }
    return {
        "type": "CommandError",
        "message": str(error),
    }


def command_result(
    command: str,
    *,
    status: CommandStatus,
    result: Any = None,
    warnings: Sequence[str] = (),
    error: Mapping[str, str] | BaseException | str | None = None,
) -> dict[str, Any]:
    """Build one response using the common command envelope."""
    if status == "error" and error is None:
        raise ValueError("An error response requires error details.")
    if status != "error" and error is not None:
        raise ValueError("Only an error response may contain error details.")

    rendered_error: dict[str, str] | None
    if error is None:
        rendered_error = None
    elif isinstance(error, Mapping):
        rendered_error = {
            "type": str(error.get("type", "CommandError")),
            "message": str(error.get("message", "")),
        }
    else:
        rendered_error = error_detail(error)

    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "result": result,
        "warnings": [str(warning) for warning in warnings],
        "error": rendered_error,
    }


def command_error(
    command: str,
    error: Mapping[str, str] | BaseException | str,
    *,
    result: Any = None,
    warnings: Sequence[str] = (),
) -> dict[str, Any]:
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


def emit_command_result(payload: Mapping[str, Any]) -> None:
    """Print exactly one command response to stdout."""
    print(json.dumps(dict(payload), indent=2, ensure_ascii=False))


__all__ = [
    "CommandStatus",
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
