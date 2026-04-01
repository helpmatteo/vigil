from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RadioButton, RadioSet, Static, Switch

if TYPE_CHECKING:
    from ..config import Config
    from ..discovery import InstanceInfo


class SetupWizardScreen(Screen[bool]):
    """Multi-step setup wizard for first-time configuration."""

    DEFAULT_CSS = """
    SetupWizardScreen {
        align: center middle;
    }

    SetupWizardScreen #wizard-container {
        width: 80;
        max-width: 95%;
        height: auto;
        max-height: 90%;
        border: solid $surface-lighten-3;
        background: $surface;
        padding: 1 2;
    }

    SetupWizardScreen #wizard-container .step-title {
        text-style: bold;
        margin-bottom: 1;
    }

    SetupWizardScreen #wizard-container .step-description {
        color: $text-muted;
        margin-bottom: 1;
    }

    SetupWizardScreen #wizard-container .step-content {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    SetupWizardScreen #wizard-container .progress {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
    }

    SetupWizardScreen #wizard-container .nav-buttons {
        height: 3;
        align: right middle;
    }

    SetupWizardScreen #wizard-container .nav-buttons Button {
        margin-left: 1;
    }

    SetupWizardScreen #wizard-container .status-ok {
        color: $success;
    }

    SetupWizardScreen #wizard-container .status-error {
        color: $error;
    }

    SetupWizardScreen #wizard-container .status-warn {
        color: $warning;
    }
    """

    BINDINGS = [
        ("q", "quit_wizard", "Quit"),
        ("escape", "prev_step", "Back"),
    ]

    STEP_LABELS = ["API Key", "SSH Key", "Framework", "Alerts", "Done"]

    def __init__(self, config: Config, http_client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        self.config = config
        self._http_client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None
        self._step = 0
        self._discovered_instances: list[InstanceInfo] = []
        self._api_validated = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="wizard-container"):
            yield Static("", classes="progress")
            yield Static("", classes="step-title")
            yield Static("", classes="step-description")
            yield Vertical(id="step-content")
            yield Static("", id="step-status")
            with Horizontal(classes="nav-buttons"):
                yield Button("Skip", id="skip-btn", variant="default")
                yield Button("Back", id="back-btn", variant="default")
                yield Button("Next", id="next-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._render_step()

    def _render_step(self) -> None:
        """Render the current step content."""
        # Update progress bar
        progress_parts = []
        for i, label in enumerate(self.STEP_LABELS):
            if i == self._step:
                progress_parts.append(f"[bold][{i + 1}] {label}[/bold]")
            elif i < self._step:
                progress_parts.append(f"[dim][{i + 1}] {label} ✓[/dim]")
            else:
                progress_parts.append(f"[dim][{i + 1}] {label}[/dim]")
        self.query_one(".progress", Static).update("  ".join(progress_parts))

        # Update nav buttons
        self.query_one("#back-btn", Button).display = self._step > 0
        self.query_one("#skip-btn", Button).display = self._step < len(self.STEP_LABELS) - 1
        next_btn = self.query_one("#next-btn", Button)
        if self._step == len(self.STEP_LABELS) - 1:
            next_btn.label = "Finish"
        else:
            next_btn.label = "Next"

        # Clear status
        self.query_one("#step-status", Static).update("")

        # Clear and rebuild step content — use call_after_refresh to ensure
        # removal completes before mounting new children.
        content = self.query_one("#step-content", Vertical)
        content.remove_children()
        self.call_after_refresh(self._mount_step_content)

    def _mount_step_content(self) -> None:
        """Mount widgets for the current step after old children are removed."""
        content = self.query_one("#step-content", Vertical)
        if self._step == 0:
            self._render_api_key_step(content)
        elif self._step == 1:
            self._render_ssh_key_step(content)
        elif self._step == 2:
            self._render_framework_step(content)
        elif self._step == 3:
            self._render_alerts_step(content)
        elif self._step == 4:
            self._render_done_step(content)

    def _render_api_key_step(self, content: Vertical) -> None:
        title = self.query_one(".step-title", Static)
        title.update("[bold]Welcome to vigil[/bold]")
        desc = self.query_one(".step-description", Static)
        desc.update(
            "Real-time TUI for monitoring Vast.ai GPU training instances.\n"
            "Press S anytime to return to this wizard."
        )

        # Pre-fill from existing config
        existing = self.config.vast_api_key or ""
        source = ""
        if existing:
            import os
            if os.environ.get("VAST_API_KEY"):
                source = "Found from VAST_API_KEY env var"
            else:
                source = "Found from config"

        content.mount(Label("Vast.ai API Key:"))
        content.mount(Input(
            value=existing,
            placeholder="Paste your API key here",
            password=True,
            id="api-key-input",
        ))
        if source:
            content.mount(Static(f"[dim]{source}[/dim]"))
        content.mount(Button("Validate", id="validate-btn", variant="primary"))

    def _render_ssh_key_step(self, content: Vertical) -> None:
        title = self.query_one(".step-title", Static)
        title.update("[bold]SSH Key[/bold]")
        desc = self.query_one(".step-description", Static)
        desc.update("Select the SSH key registered with your Vast.ai account.")

        # Scan for SSH keys
        ssh_dir = Path.home() / ".ssh"
        candidates = ["id_vastai", "id_rsa", "id_ed25519", "id_ecdsa"]
        found = []
        for name in candidates:
            path = ssh_dir / name
            if path.exists():
                found.append(path)

        current = str(self.config.ssh_key_path)

        if found:
            content.mount(Label("Found SSH keys:"))
            buttons = []
            for path in found:
                is_selected = str(path) == current
                buttons.append(RadioButton(str(path), value=is_selected))
            content.mount(RadioSet(*buttons, id="ssh-key-radio"))
        else:
            content.mount(Label("No SSH keys found in ~/.ssh/"))
            content.mount(Input(
                value=current,
                placeholder="Path to SSH private key",
                id="ssh-key-input",
            ))
            content.mount(Static("[dim]Generate one with: ssh-keygen -t ed25519[/dim]"))

        content.mount(Static("[dim]Make sure this key is registered in your Vast.ai account settings.[/dim]"))

    def _render_framework_step(self, content: Vertical) -> None:
        title = self.query_one(".step-title", Static)
        title.update("[bold]Framework Preset[/bold]")
        desc = self.query_one(".step-description", Static)
        desc.update("Choose a preset to optimize metric parsing for your training framework.")

        from ..presets import PRESETS

        buttons = [
            RadioButton(f"{preset['label']} — {preset['description']}")
            for preset in PRESETS.values()
        ]
        buttons.append(RadioButton("Custom — keep defaults"))
        content.mount(RadioSet(*buttons, id="preset-radio"))

        # If we have instances, offer auto-detect
        if self._discovered_instances:
            content.mount(Button("Auto-detect from running instance", id="autodetect-btn", variant="default"))

    def _render_alerts_step(self, content: Vertical) -> None:
        title = self.query_one(".step-title", Static)
        title.update("[bold]Alerts & Notifications[/bold]")
        desc = self.query_one(".step-description", Static)
        desc.update("Configure how you want to be notified about training issues.")

        content.mount(Horizontal(
            Label("Desktop notifications: "),
            Switch(value=self.config.notifications.desktop, id="desktop-switch"),
        ))

        content.mount(Label("Stall threshold (minutes of no output):"))
        content.mount(Input(
            value=str(self.config.stall_threshold_minutes),
            placeholder="5",
            id="stall-input",
        ))

        content.mount(Label("Webhook URL (optional):"))
        content.mount(Input(
            value=self.config.alert_webhook_url or "",
            placeholder="https://hooks.slack.com/services/...",
            id="webhook-input",
        ))

        content.mount(Label("Webhook format:"))
        fmt_buttons = [
            RadioButton(fmt, value=(fmt == self.config.alert_webhook_format))
            for fmt in ["raw", "slack", "discord"]
        ]
        content.mount(RadioSet(*fmt_buttons, id="webhook-format-radio"))

    def _render_done_step(self, content: Vertical) -> None:
        title = self.query_one(".step-title", Static)
        title.update("[bold]Setup Complete[/bold]")
        desc = self.query_one(".step-description", Static)

        n = len(self._discovered_instances)
        if n > 0:
            desc.update(f"Monitoring {n} instance{'s' if n != 1 else ''}.")
        else:
            desc.update("No running instances found — will poll automatically.")

        # Summary
        summary_lines = []
        if self.config.vast_api_key:
            summary_lines.append("[green]✓[/green] API key configured")
        else:
            summary_lines.append("[yellow]○[/yellow] API key not set — add via S wizard later")
        summary_lines.append(f"[green]✓[/green] SSH key: {self.config.ssh_key_path}")
        if self.config.extra_metric_patterns:
            n_extra = len(self.config.extra_metric_patterns)
            summary_lines.append(f"[green]✓[/green] Framework preset applied ({n_extra} extra patterns)")
        else:
            summary_lines.append("[dim]○[/dim] Using default metric patterns")
        desktop_status = "on" if self.config.notifications.desktop else "off"
        summary_lines.append(f"[green]✓[/green] Desktop notifications: {desktop_status}")
        if self.config.alert_webhook_url:
            summary_lines.append(f"[green]✓[/green] Webhook: {self.config.alert_webhook_format} format")

        content.mount(Static("\n".join(summary_lines), markup=True))
        content.mount(Static("\n[dim]Press Enter or Finish to launch the dashboard.[/dim]", markup=True))

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next-btn":
            self._save_current_step()
            if self._step < len(self.STEP_LABELS) - 1:
                self._step += 1
                self._render_step()
            else:
                self._finish()
        elif event.button.id == "back-btn":
            if self._step > 0:
                self._save_current_step()
                self._step -= 1
                self._render_step()
        elif event.button.id == "skip-btn":
            if self._step < len(self.STEP_LABELS) - 1:
                self._step += 1
                self._render_step()
        elif event.button.id == "validate-btn":
            self.run_worker(self._validate_api_key(), exclusive=True, group="validate")
        elif event.button.id == "autodetect-btn":
            self.run_worker(self._auto_detect_framework(), exclusive=True, group="detect")

    def _save_current_step(self) -> None:
        """Save the current step's values to config."""
        if self._step == 0:
            # API key
            try:
                inp = self.query_one("#api-key-input", Input)
                if inp.value:
                    self.config.vast_api_key = inp.value
            except Exception:
                pass
        elif self._step == 1:
            # SSH key
            try:
                radio = self.query_one("#ssh-key-radio", RadioSet)
                pressed = radio.pressed_button
                if pressed is not None:
                    self.config.ssh_key_path = Path(pressed.label.plain)
            except Exception:
                try:
                    inp = self.query_one("#ssh-key-input", Input)
                    if inp.value:
                        self.config.ssh_key_path = Path(inp.value).expanduser()
                except Exception:
                    pass
        elif self._step == 2:
            # Framework preset
            try:
                radio = self.query_one("#preset-radio", RadioSet)
                from ..presets import PRESETS, apply_preset
                keys = list(PRESETS.keys())
                idx = radio.pressed_index
                if idx >= 0 and idx < len(keys):
                    apply_preset(self.config, keys[idx])
                # else: Custom — do nothing
            except Exception:
                pass
        elif self._step == 3:
            # Alerts
            try:
                switch = self.query_one("#desktop-switch", Switch)
                self.config.notifications.desktop = switch.value
                # Keep legacy field in sync to avoid backward-compat revert
                self.config.desktop_notifications = switch.value
            except Exception:
                pass
            try:
                stall_inp = self.query_one("#stall-input", Input)
                if stall_inp.value:
                    self.config.stall_threshold_minutes = int(stall_inp.value)
            except (Exception, ValueError):
                pass
            try:
                webhook_inp = self.query_one("#webhook-input", Input)
                self.config.alert_webhook_url = webhook_inp.value or None
            except Exception:
                pass
            try:
                fmt_radio = self.query_one("#webhook-format-radio", RadioSet)
                formats = ["raw", "slack", "discord"]
                idx = fmt_radio.pressed_index
                if 0 <= idx < len(formats):
                    self.config.alert_webhook_format = formats[idx]
            except Exception:
                pass

    async def _validate_api_key(self) -> None:
        status = self.query_one("#step-status", Static)
        inp = self.query_one("#api-key-input", Input)
        key = inp.value.strip()
        if not key:
            status.update("[red]Please enter an API key[/red]")
            return

        status.update("[dim]Validating...[/dim]")
        try:
            from ..discovery import fetch_instances, RateLimitError
            self.config.vast_api_key = key
            result = await fetch_instances(key, self._http_client)
            self._discovered_instances = result.running
            self._api_validated = True
            n = len(result.running)
            status.update(f"[green]✓ Connected — {n} running instance{'s' if n != 1 else ''} found[/green]")
        except RateLimitError:
            status.update("[yellow]⚠ Rate limited — key saved, will retry on launch[/yellow]")
            self._api_validated = True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                status.update("[red]✗ Invalid API key — check your Vast.ai dashboard[/red]")
            else:
                status.update(f"[red]✗ API error: {exc.response.status_code}[/red]")
        except Exception:
            status.update("[yellow]⚠ Could not reach Vast.ai API — key saved, will retry on launch[/yellow]")
            self._api_validated = True

    async def _auto_detect_framework(self) -> None:
        status = self.query_one("#step-status", Static)
        if not self._discovered_instances:
            status.update("[yellow]No running instances to scan[/yellow]")
            return

        inst = self._discovered_instances[0]
        status.update(f"[dim]Scanning instance #{inst.id} logs for 5 seconds...[/dim]")

        try:
            from ..ssh import ssh_connect
            conn = await ssh_connect(inst, self.config, keepalive=False)
            lines: list[str] = []
            async with conn:
                command = self.config.log_command_for(inst.id)
                async with conn.create_process(command) as process:
                    try:
                        async with asyncio.timeout(5):
                            async for line in process.stdout:
                                lines.append(line.rstrip("\n\r"))
                    except (asyncio.TimeoutError, TimeoutError):
                        pass

            from ..presets import detect_framework, PRESETS
            detected = detect_framework(lines)
            if detected:
                label = PRESETS[detected]["label"]
                status.update(f"[green]✓ Detected: {label} — select it above to apply[/green]")
                # Store detection result for _save_current_step to use
                self._detected_preset = detected
            else:
                status.update("[dim]Could not detect framework — please select manually[/dim]")
        except Exception:
            status.update("[dim]Could not connect — please select manually[/dim]")

    def _finish(self) -> None:
        self._save_current_step()
        self.config.save_config()
        if self._owns_client:
            self.run_worker(self._http_client.aclose(), exit_on_error=False)
        self.dismiss(True)

    def action_quit_wizard(self) -> None:
        self.config.save_config()
        if self._owns_client:
            self.run_worker(self._http_client.aclose(), exit_on_error=False)
        self.dismiss(False)

    def action_prev_step(self) -> None:
        if self._step > 0:
            self._save_current_step()
            self._step -= 1
            self._render_step()
        else:
            self.action_quit_wizard()
