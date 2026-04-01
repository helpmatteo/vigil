from __future__ import annotations

from dataclasses import dataclass

import httpx

VAST_API_BASE = "https://console.vast.ai/api/v0"


class RateLimitError(Exception):
    def __init__(self, retry_after: float = 60.0):
        self.retry_after = retry_after


@dataclass
class InstanceInfo:
    id: int
    ssh_host: str
    ssh_port: int
    gpu_name: str
    num_gpus: int
    status: str
    machine_id: int
    label: str | None = None
    dph_total: float = 0.0


@dataclass
class DiscoveryResult:
    running: list[InstanceInfo]
    stuck: list[InstanceInfo]


async def fetch_instances(
    api_key: str, client: httpx.AsyncClient
) -> DiscoveryResult:
    resp = await client.get(
        f"{VAST_API_BASE}/instances/",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=httpx.Timeout(10.0, connect=5.0),
    )
    if resp.status_code == 429:
        retry_after = float(resp.headers.get("Retry-After", "60"))
        raise RateLimitError(retry_after)
    resp.raise_for_status()
    data = resp.json()

    running: list[InstanceInfo] = []
    stuck: list[InstanceInfo] = []
    for inst in data.get("instances", []):
        try:
            is_running = inst.get("actual_status") == "running"
            has_ssh = bool(inst.get("ssh_host")) and bool(inst.get("ssh_port"))
            info = InstanceInfo(
                id=inst["id"],
                ssh_host=inst.get("ssh_host") or "",
                ssh_port=int(inst.get("ssh_port") or 0),
                gpu_name=inst.get("gpu_name", "Unknown GPU"),
                num_gpus=int(inst.get("num_gpus", 1)),
                status=inst.get("actual_status", "unknown"),
                machine_id=int(inst.get("machine_id", 0)),
                label=inst.get("label"),
                dph_total=float(inst.get("dph_total", 0.0)),
            )
            terminal = info.status in {"exited", "destroyed", "deleting", "error"}
            if is_running and has_ssh:
                running.append(info)
            elif not terminal:
                stuck.append(info)
        except (KeyError, ValueError, TypeError):
            continue

    return DiscoveryResult(running=running, stuck=stuck)


async def fetch_credit(
    api_key: str, client: httpx.AsyncClient
) -> float | None:
    """Return account credit balance, or None on failure."""
    try:
        resp = await client.get(
            f"{VAST_API_BASE}/users/current/",
            params={"owner": "me"},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        if resp.status_code == 429:
            return None
        resp.raise_for_status()
        return float(resp.json().get("credit", 0.0))
    except Exception:
        return None


async def destroy_instance(
    api_key: str, instance_id: int, client: httpx.AsyncClient
) -> None:
    resp = await client.delete(
        f"{VAST_API_BASE}/instances/{instance_id}/",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=httpx.Timeout(10.0, connect=5.0),
    )
    resp.raise_for_status()
