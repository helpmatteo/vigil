from __future__ import annotations

import asyncio
import sys


async def send_desktop_notification(title: str, body: str) -> None:
    """Send an OS-level desktop notification. Best-effort, never raises."""
    proc: asyncio.subprocess.Process | None = None
    try:
        if sys.platform == "darwin":
            script = (
                f'display notification "{_escape_applescript(body)}"'
                f' with title "{_escape_applescript(title)}"'
            )
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        elif sys.platform == "linux":
            proc = await asyncio.create_subprocess_exec(
                "notify-send", title, body,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        if proc is not None and proc.returncode is None:
            proc.kill()
            await proc.wait()
    except Exception:
        pass  # Best effort — never disrupt the app
    finally:
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass


def _escape_applescript(s: str) -> str:
    """Escape special characters for AppleScript string literals."""
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", " ").replace("\r", " ")
    return s
