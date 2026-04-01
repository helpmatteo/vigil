from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config
from .providers import get_provider


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
        "--provider",
        type=str,
        default="vast",
        choices=["vast", "runpod"],
        help="GPU cloud provider (default: vast)",
    )
    parser.add_argument(
        "--reset-hints",
        action="store_true",
        help="Reset onboarding hints so they appear again",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with simulated GPU instances (no API key or SSH needed)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    config.provider = args.provider
    provider = get_provider(config.provider)

    # Re-resolve API key now that provider is known (checks RUNPOD_API_KEY, etc.)
    if not config.api_key:
        from .config import _resolve_api_key
        _resolve_api_key(config, provider)

    if args.api_key:
        config.api_key = args.api_key

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
    from .app import Dashboard

    app = Dashboard(config, state, provider=provider, demo=args.demo)
    app.run()


if __name__ == "__main__":
    main()
