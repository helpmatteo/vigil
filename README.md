# vigil

**Real-time TUI for monitoring cloud GPU training instances.**

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![PyPI](https://img.shields.io/badge/pypi-vigil-orange)

> **TL;DR** — `pip install vigil-gpu && vigil`. A single terminal command gives you live SSH log streaming from every cloud GPU instance, regex-parsed metrics with sparklines, NaN/stall/plateau alerts to desktop or Slack/Discord, nvidia-smi on demand, persistent logs that survive crashes, and a setup wizard that auto-detects your framework. All from a keyboard-driven TUI.

<!-- TODO: Replace with an actual screenshot or asciinema recording -->
<!-- ![vigil demo](docs/demo.gif) -->

## The Problem

Cloud GPU consoles (Vast.ai, RunPod, Lambda, etc.) provide delayed, truncated output and offer no log persistence when instances crash or are preempted. If you are running multiple GPU training jobs across rented instances, you need a tool that streams logs in real time, survives disconnections, and alerts you before a stalled run burns through your budget.

## Supported Providers

- **Vast.ai** — full support (auto-discovery, instance management, cost tracking)
- More providers planned (RunPod, Lambda Labs, etc.)

## Features

### Live Monitoring

- Auto-discovers all running instances via provider APIs
- Streams logs in real time over SSH with automatic reconnection and exponential backoff
- Dynamic grid layout that adapts columns to instance count (1/2/3 columns, configurable max)
- Per-instance panels showing GPU type, count, label, and hourly cost
- Aggregate cost display across all instances in the subtitle bar
- Focus mode: select a panel to expand it to full width
- Pause/resume log rendering and toggle auto-scroll per panel

### Metric Parsing
- Configurable regex patterns with named capture groups
- 10 built-in patterns: loss, step, epoch, learning rate, reward, accuracy, RSSM, VC, TOM, actor
- Inline sparkline charts (Unicode block elements) showing metric trends over time
- Color-coded direction indicators (green/red based on whether up or down is desirable)
- NaN/Inf detection with immediate alerting
- Loss plateau detection using rolling standard deviation
- Keyword pre-filtering for efficient pattern matching at scale

### Framework Presets

- **HuggingFace Transformers**: eval_loss, train_loss, learning_rate, eval_accuracy, grad_norm, samples_sec
- **PyTorch Lightning**: val_loss, train_loss, val_acc, train_acc
- **DreamerV3 / RL**: ep_return, episode, fps, policy_loss, value_loss, model_loss
- Auto-detection from running instance logs (samples 5 seconds of output to identify framework)
- Apply via setup wizard or configure manually

### Alerts
- Stall detection when no output is received for a configurable duration
- NaN/Inf alerts with visual panel highlighting (red border)
- Loss plateau alerts using sliding-window standard deviation (configurable window and threshold)
- Desktop notifications on macOS (osascript) and Linux (notify-send)
- Webhook integration with Slack (Block Kit), Discord (embeds), and raw JSON formats
- Per-alert-type notification control (NaN, plateau, stall independently togglable)
- Alerts auto-clear when values return to normal
- All notifications are best-effort and non-blocking (never disrupt the TUI)

### Instance Management

- Instance manager view with GPU details, costs, connection status, and SSH commands
- Live nvidia-smi output over SSH (with manual refresh)
- Change the log command per instance at runtime (persisted to config)
- Stop/destroy instances directly from the TUI (with confirmation dialog showing instance details)
- Force SSH reconnect with manual trigger
- Configurable SSH username (global and per-instance)
- SSH keepalive and connection timeout settings

### Log Persistence

- All logs written to `~/.vigil/logs/` with per-instance directories
- Timestamped raw log files with atomic `latest.log` symlink
- Metrics JSONL sidecar files for post-hoc analysis
- Historical log browser with session list and search
- Crash-resilient: logs are buffered and flushed periodically (every 10s) and on disconnect
- Configurable log retention by age (days) and total size (MB)
- Automatic hourly cleanup of expired log sessions

### Search
- Inline log filtering with `/` (regex-supported, debounced)
- Global cross-instance search with `G` (searches all in-memory log buffers, up to 100 results per instance)
- Historical log search in the log viewer
- Graceful regex fallback to substring matching on invalid patterns

### Metrics Comparison

- Full-screen metrics table comparing all instances side by side
- Dynamic columns based on collected metrics across all instances
- Sparklines and direction indicators per metric per instance
- Auto-refreshes every 2 seconds with manual refresh option

### Setup Wizard

- Guided 5-step onboarding wizard for first-time setup
- **Step 1**: API key input with live validation (tests connectivity and shows instance count)
- **Step 2**: SSH key selection with auto-detection of common key paths
- **Step 3**: Framework preset selection with auto-detection from running instances
- **Step 4**: Alert and notification configuration (desktop, stall threshold, webhooks)
- **Step 5**: Summary and confirmation before launch
- Progress bar and back/skip/next navigation
- Accessible anytime with `S` (Shift+S)

### Contextual Hints

- Non-intrusive hint bar with sequenced tips for new users
- Covers: focusing panels, searching logs, viewing help, comparing metrics
- Auto-dismisses after 30 seconds, respects minimum instance requirements
- Tracks completion in persistent state; reset with `--reset-hints`

## Quick Start

```bash
pip install vigil-gpu
vigil
```

If this is your first run, the setup wizard will guide you through configuration. Otherwise, provide your API key via any of these methods (checked in order):

1. **CLI flag**: `vigil --api-key YOUR_KEY`
2. **Environment variable**: `VIGIL_API_KEY=YOUR_KEY vigil`
3. **Config file**: Set `api_key` in `~/.config/vigil/config.yaml`
4. **Vast CLI default**: Place your key in `~/.vast_api_key`

### CLI Options

```text
vigil [OPTIONS]

  --config, -c PATH    Config file path (default: ~/.config/vigil/config.yaml)
  --api-key KEY        Provider API key (overrides config/env)
  --provider NAME      GPU provider (default: vast) [vast]
  --reset-hints        Reset onboarding hints so they appear again
```

## Configuration

Configuration lives at `~/.config/vigil/config.yaml`. All fields are optional with sensible defaults. See [`config.example.yaml`](config.example.yaml) for the full reference.

### Key Settings

```yaml
# GPU cloud provider
provider: vast

# Provider API key (prefer env var for security)
api_key: null

# Seconds between API polls for instance changes
poll_interval: 30

# Local directory for persistent logs
log_dir: "~/.vigil/logs"

# SSH private key path
ssh_key_path: "~/.ssh/id_ed25519"

# Minutes of silence before stall alert fires
stall_threshold_minutes: 5

# Desktop notifications for NaN/plateau/stall alerts
desktop_notifications: true

# Webhook URL for alerts (receives JSON POST)
alert_webhook_url: null
```

### SSH Settings

```yaml
ssh_username: "root"
ssh_login_timeout: 10        # seconds
ssh_keepalive_interval: 15   # seconds (0 to disable)
reconnect_backoff_max: 60    # max seconds between reconnect attempts
```

### Log Retention

```yaml
log_retention_days: 0   # delete logs older than N days (0 = keep forever)
log_max_size_mb: 0      # max total log storage in MB (0 = unlimited)
```

### Layout & Buffers

```yaml
max_grid_columns: 3       # max columns in the instance grid
log_buffer_lines: 5000    # in-memory log buffer per instance
log_display_lines: 2000   # max lines rendered in the panel
highlight_logs: false     # Rich syntax highlighting on log lines
sparkline_history: 60     # metric readings kept for sparkline rendering
```

### Custom Metric Patterns

Metrics are extracted from log lines using regex patterns with named capture groups. The group name becomes the metric key displayed in the panel.

```yaml
metric_patterns:
  - 'loss[:\s=]+(?P<loss>[\d.]+)'
  - 'step[:\s=]+(?P<step>\d+(?:,\d{3})*)'
  - 'epoch[:\s=]+(?P<epoch>[\d./]+)'
  - '(?<![a-z])lr[:\s=]+(?P<lr>[\d.e\-]+)'
  - 'reward[:\s=]+(?P<reward>[\d.\-e]+)'
  - 'accuracy[:\s=]+(?P<accuracy>[\d.]+)'
```

These are a subset of the 10 built-in defaults. Setting `metric_patterns` in your config **replaces** all defaults. To add patterns without replacing, use `extra_metric_patterns`:

```yaml
extra_metric_patterns:
  - 'val_loss[:\s=]+(?P<val_loss>[\d.]+)'
  - 'perplexity[:\s=]+(?P<ppl>[\d.]+)'
```

### Metric Semantics

Control which metrics get green/red coloring and which are treated as counters:

```yaml
decrease_good: [loss, val_loss, rssm, vc, tom, ppl]
increase_good: [reward, accuracy, val_accuracy]
counters: [step, epoch]
plateau_metrics: [loss, val_loss]
```

### Plateau Detection

```yaml
plateau_window: 8          # number of readings to check
plateau_threshold: 0.0001  # stdev below this = plateau
plateau_metrics: [loss]    # which metrics to watch
```

### Webhook Alerts

Supports raw JSON, Slack Block Kit, and Discord embed formats:

```yaml
alert_webhook_url: "https://hooks.slack.com/services/..."
alert_webhook_format: "slack"  # "raw", "slack", or "discord"

notifications:
  nan: true        # NaN/Inf detected in metrics
  plateau: true    # Loss plateau detected
  stall: true      # No output for configured minutes
  desktop: true    # Master switch for OS desktop notifications
  webhook: true    # Master switch for webhook alerts
```

### Per-Instance Overrides

```yaml
instances:
  12345:
    log_command: "tail -f /workspace/training.log"
    stall_threshold_minutes: 10
    ssh_username: "trainer"
  67890:
    log_command: "docker logs -f training_container"
```

## Keyboard Shortcuts

### Navigation

| Key       | Action                                      |
|-----------|---------------------------------------------|
| `1`-`9`   | Focus/unfocus instance panel by number      |
| `Tab`     | Cycle to next panel                         |
| `Escape`  | Back / unfocus panel / close search         |
| `?`       | Toggle help overlay                         |
| `q`       | Quit                                        |

### Views

| Key       | Action                                      |
|-----------|---------------------------------------------|
| `i`       | Instance manager (details, SSH commands)    |
| `l`       | Historical log viewer (with search)         |
| `m`       | Metrics comparison table (auto-refreshes)   |
| `G`       | Global search across all instances          |
| `n`       | nvidia-smi output for focused instance      |
| `S`       | Open setup wizard                           |

### Instance Actions (focus a panel first)

| Key       | Action                                      |
|-----------|---------------------------------------------|
| `c`       | Change log command for focused instance     |
| `r`       | Force SSH reconnect                         |
| `D`       | Stop/destroy instance (requires confirmation)|

### Log Control (focus a panel first)

| Key       | Action                                      |
|-----------|---------------------------------------------|
| `/`       | Search / filter logs (regex supported)      |
| `p`       | Pause / resume log rendering                |
| `f`       | Toggle auto-scroll follow mode              |

## How It Works

```text
┌─────────────────────────────────────────────────────┐
│              Provider API (Vast.ai, ...)            │
│            (instance discovery loop)                │
└──────────────────────┬──────────────────────────────┘
                       │ poll every N seconds
                       ▼
┌─────────────────────────────────────────────────────┐
│              Discovery / Reconciler                 │
│     adds new instances, removes terminated ones     │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ SSH Log │  │ SSH Log │  │ SSH Log │  ... per instance
   │ Stream  │  │ Stream  │  │ Stream  │
   └────┬────┘  └────┬────┘  └────┬────┘
        │             │            │
        ▼             ▼            ▼
   ┌──────────────────────────────────────────────────┐
   │              Metric Parser                       │
   │   regex extraction → metric state + history      │
   └──────────────────────┬───────────────────────────┘
        │                 │                │
        ▼                 ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────────┐
   │ Log      │    │ Alert    │    │ TUI Panels   │
   │ Storage  │    │ Engine   │    │ (Textual)    │
   │ (disk)   │    │          │    │              │
   └──────────┘    └────┬─────┘    └──────────────┘
                        │
              ┌─────────┼──────────┐
              ▼         ▼          ▼
         ┌────────┐ ┌───────┐ ┌────────┐
         │Desktop │ │Webhook│ │ Visual │
         │Notif.  │ │(Slack/│ │ Alert  │
         │        │ │Discord│ │(border)│
         └────────┘ └───────┘ └────────┘
```

Vigil runs a discovery loop that polls your GPU provider's API at a configurable interval to find running instances. For each discovered instance, it opens a persistent SSH connection and executes a log command (a smart heuristic that finds training process stdout, recent log files, or provider-specific logs). Each line is fed through a regex-based metric parser, written to local storage (raw log + metrics JSONL sidecar), and rendered in a Textual TUI panel with sparklines and color-coded metric indicators. A background alert engine monitors each stream for stalls, NaN values, and plateaus. When instances are added or removed, the grid layout and SSH connections are reconciled automatically.

All I/O is async. SSH connections use keepalive heartbeats and reconnect with exponential backoff. Log files are buffered and flushed periodically. Notifications and webhooks are fire-and-forget to never block the UI.

## Requirements

- **Python 3.10+**
- **SSH key** registered with your GPU provider (default: `~/.ssh/id_ed25519`)
- Dependencies: [textual](https://github.com/Textualize/textual), [asyncssh](https://github.com/ronf/asyncssh), [httpx](https://github.com/encode/httpx), [pyyaml](https://github.com/yaml/pyyaml)

## Development

```bash
git clone https://github.com/vigil-gpu/vigil.git
cd vigil
python -m venv .venv && source .venv/bin/activate
pip install -e .
vigil --config config.example.yaml
```

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT. See [LICENSE](LICENSE).
