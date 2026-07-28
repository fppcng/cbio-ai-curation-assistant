from __future__ import annotations

import unittest

from cbio_curation_assistant.command_result import (
    EXIT_ERROR,
    EXIT_PARTIAL_SUCCESS,
    EXIT_SUCCESS,
    EXIT_USAGE,
    command_error,
    command_result,
    exit_code_for_status,
)


class CommandResultTest(unittest.TestCase):
    def test_success_uses_the_shared_envelope(self) -> None:
        payload = command_result(
            "example",
            status="success",
            result={"value": 1},
        )

        self.assertEqual(
            payload,
            {
                "schema_version": 1,
                "command": "example",
                "status": "success",
                "result": {"value": 1},
                "warnings": [],
                "error": None,
            },
        )

    def test_partial_success_keeps_warnings_outside_the_result(self) -> None:
        payload = command_result(
            "example",
            status="partial_success",
            result={"candidate": "/attempt/output.txt"},
            warnings=["candidate was not promoted"],
        )

        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["warnings"], ["candidate was not promoted"])
        self.assertIsNone(payload["error"])

    def test_error_has_stable_type_and_message_fields(self) -> None:
        payload = command_error("example", RuntimeError("broken"))

        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["error"],
            {"type": "RuntimeError", "message": "broken"},
        )

    def test_statuses_map_to_the_agreed_exit_codes(self) -> None:
        self.assertEqual(exit_code_for_status("success"), EXIT_SUCCESS)
        self.assertEqual(exit_code_for_status("error"), EXIT_ERROR)
        self.assertEqual(
            exit_code_for_status("partial_success"),
            EXIT_PARTIAL_SUCCESS,
        )
        self.assertEqual(
            (EXIT_SUCCESS, EXIT_ERROR, EXIT_USAGE, EXIT_PARTIAL_SUCCESS),
            (0, 1, 2, 3),
        )

    def test_invalid_error_combinations_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            command_result("example", status="error")
        with self.assertRaises(ValueError):
            command_result("example", status="success", error="unexpected")


if __name__ == "__main__":
    unittest.main()
