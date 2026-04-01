from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Real-time TUI for monitoring cloud GPU training instances",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=None,
        help=f"Config file path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Provider API key (overrides config/env)",
    )
    parser.add_argument(
        "--reset-hints",
        action="store_true",
        help="Reset onboarding hints so they appear again",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.api_key:
        config.vast_api_key = args.api_key

    # Handle --reset-hints
    if args.reset_hints:
        from .state import load_state
        state = load_state()
        state.reset()
        print("Onboarding hints have been reset.")
        return

    # Load UI state
    from .state import load_state
    state = load_state()

    # No longer exit on missing API key — the wizard will handle it
    from .app import VastDashboard

    app = VastDashboard(config, state)
    app.run()


if __name__ == "__main__":
    main()
