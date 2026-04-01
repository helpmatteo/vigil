from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vigil.notifications import _escape_applescript, send_desktop_notification


# ---------------------------------------------------------------------------
# _escape_applescript
# ---------------------------------------------------------------------------


class TestEscapeApplescript:
    def test_escapes_backslashes(self):
        assert _escape_applescript("a\\b") == "a\\\\b"

    def test_escapes_double_quotes(self):
        assert _escape_applescript('say "hello"') == 'say \\"hello\\"'

    def test_escapes_newlines(self):
        assert _escape_applescript("line1\nline2") == "line1 line2"

    def test_escapes_carriage_returns(self):
        assert _escape_applescript("line1\rline2") == "line1 line2"

    def test_escapes_mixed(self):
        assert _escape_applescript('a\\b\n"c"\rd') == 'a\\\\b \\"c\\" d'

    def test_empty_string(self):
        assert _escape_applescript("") == ""

    def test_no_special_chars(self):
        assert _escape_applescript("plain text") == "plain text"

    def test_backslash_before_quote(self):
        assert _escape_applescript('\\"') == '\\\\\\"'

    def test_multiple_newlines(self):
        assert _escape_applescript("\n\n\n") == "   "


# ---------------------------------------------------------------------------
# send_desktop_notification — darwin path
# ---------------------------------------------------------------------------


class TestSendDesktopNotificationDarwin:
    @pytest.mark.anyio
    async def test_calls_osascript_on_darwin(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
            patch("vigil.notifications.asyncio.wait_for", return_value=0),
        ):
            mock_sys.platform = "darwin"
            await send_desktop_notification("Test Title", "Test Body")

        mock_exec.assert_awaited_once()
        args = mock_exec.call_args[0]
        assert args[0] == "osascript"
        assert args[1] == "-e"
        assert "display notification" in args[2]
        assert "Test Body" in args[2]
        assert "Test Title" in args[2]

    @pytest.mark.anyio
    async def test_darwin_escapes_special_chars_in_args(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
            patch("vigil.notifications.asyncio.wait_for", return_value=0),
        ):
            mock_sys.platform = "darwin"
            await send_desktop_notification('Title "quoted"', "Body\nwith newline")

        script = mock_exec.call_args[0][2]
        assert '\\"' in script
        assert "\n" not in script


# ---------------------------------------------------------------------------
# send_desktop_notification — linux path
# ---------------------------------------------------------------------------


class TestSendDesktopNotificationLinux:
    @pytest.mark.anyio
    async def test_calls_notify_send_on_linux(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
            patch("vigil.notifications.asyncio.wait_for", return_value=0),
        ):
            mock_sys.platform = "linux"
            await send_desktop_notification("Alert", "Something happened")

        mock_exec.assert_awaited_once()
        args = mock_exec.call_args[0]
        assert args[0] == "notify-send"
        assert args[1] == "Alert"
        assert args[2] == "Something happened"


# ---------------------------------------------------------------------------
# send_desktop_notification — error handling
# ---------------------------------------------------------------------------


class TestSendDesktopNotificationErrors:
    @pytest.mark.anyio
    async def test_swallows_generic_exception(self):
        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch(
                "vigil.notifications.asyncio.create_subprocess_exec",
                side_effect=OSError("command not found"),
            ),
        ):
            mock_sys.platform = "darwin"
            await send_desktop_notification("Title", "Body")

    @pytest.mark.anyio
    async def test_swallows_file_not_found_error(self):
        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch(
                "vigil.notifications.asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("osascript not found"),
            ),
        ):
            mock_sys.platform = "darwin"
            await send_desktop_notification("Title", "Body")

    @pytest.mark.anyio
    async def test_timeout_kills_process(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock(return_value=-9)

        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("vigil.notifications.asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            mock_sys.platform = "darwin"
            await send_desktop_notification("Title", "Body")

        mock_proc.kill.assert_called()

    @pytest.mark.anyio
    async def test_timeout_with_already_finished_process(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("vigil.notifications.asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            mock_sys.platform = "darwin"
            await send_desktop_notification("Title", "Body")

        mock_proc.kill.assert_not_called()

    @pytest.mark.anyio
    async def test_unsupported_platform_does_nothing(self):
        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec") as mock_exec,
        ):
            mock_sys.platform = "win32"
            await send_desktop_notification("Title", "Body")

        mock_exec.assert_not_awaited()

    @pytest.mark.anyio
    async def test_finally_kills_proc_if_still_running(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with (
            patch("vigil.notifications.sys") as mock_sys,
            patch("vigil.notifications.asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("vigil.notifications.asyncio.wait_for", side_effect=RuntimeError("unexpected")),
        ):
            mock_sys.platform = "linux"
            await send_desktop_notification("Title", "Body")

        mock_proc.kill.assert_called()
