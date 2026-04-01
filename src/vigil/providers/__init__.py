from __future__ import annotations

from pathlib import Path
from typing import Protocol

import httpx

from ..discovery import DiscoveryResult, InstanceInfo, RateLimitError

__all__ = ["Provider", "get_provider", "DiscoveryResult", "InstanceInfo", "RateLimitError"]


class Provider(Protocol):
    name: str
    display_name: str

    async def fetch_instances(
        self, api_key: str, client: httpx.AsyncClient,
    ) -> DiscoveryResult:
        ...

    async def fetch_credit(
        self, api_key: str, client: httpx.AsyncClient,
    ) -> float | None:
        ...

    async def destroy_instance(
        self, api_key: str, instance_id: int | str, client: httpx.AsyncClient,
    ) -> None:
        ...

    def env_var_names(self) -> list[str]:
        ...

    def api_key_file(self) -> Path | None:
        ...

    def default_ssh_key_path(self) -> Path:
        ...

    def default_ssh_username(self) -> str:
        ...

    def default_log_command(self) -> str:
        ...


def get_provider(name: str) -> Provider:
    if name == "vast":
        from .vast import VastProvider

        return VastProvider()
    if name == "runpod":
        from .runpod import RunPodProvider

        return RunPodProvider()
    raise ValueError(f"Unknown provider: {name!r}. Supported: 'vast', 'runpod'")
