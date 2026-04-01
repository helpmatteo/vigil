from __future__ import annotations

import time
from typing import Any

import httpx

from .discovery import InstanceInfo


def _format_raw(
    instance_id: int,
    alert_type: str,
    message: str,
    metrics: dict[str, str] | None = None,
    instance: InstanceInfo | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "timestamp": time.time(),
        "instance_id": instance_id,
        "alert_type": alert_type,
        "message": message,
    }
    if metrics is not None:
        payload["metrics"] = metrics
    if instance:
        payload["gpu_name"] = instance.gpu_name
        payload["num_gpus"] = instance.num_gpus
        payload["dph_total"] = instance.dph_total
    return payload


def _format_slack(
    instance_id: int,
    alert_type: str,
    message: str,
    metrics: dict[str, str] | None = None,
    instance: InstanceInfo | None = None,
) -> dict[str, Any]:
    title = f"Vast.ai Alert: #{instance_id}"
    details = message
    if instance:
        details += f"\nGPU: {instance.gpu_name} x{instance.num_gpus} | ${instance.dph_total:.3f}/hr"
    if metrics is not None:
        metric_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        details += f"\nMetrics: {metric_str}"

    return {
        "text": title,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{alert_type.upper()}* — Instance #{instance_id}\n{details}",
                },
            }
        ],
    }


def _format_discord(
    instance_id: int,
    alert_type: str,
    message: str,
    metrics: dict[str, str] | None = None,
    instance: InstanceInfo | None = None,
) -> dict[str, Any]:
    # Red for errors, orange for warnings
    # Orange for known warning types, red for everything else (errors + unknown)
    _WARN_TYPES = {"low_gpu", "slow"}
    color = 16744448 if alert_type in _WARN_TYPES else 16711680
    fields = []
    if instance:
        fields.append({"name": "GPU", "value": f"{instance.gpu_name} x{instance.num_gpus}", "inline": True})
        fields.append({"name": "Cost", "value": f"${instance.dph_total:.3f}/hr", "inline": True})
    if metrics is not None:
        metric_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        fields.append({"name": "Metrics", "value": metric_str, "inline": False})

    return {
        "embeds": [
            {
                "title": f"Vast.ai Alert: #{instance_id}",
                "description": message,
                "color": color,
                "fields": fields,
                "footer": {"text": alert_type},
            }
        ]
    }


_FORMATTERS = {
    "raw": _format_raw,
    "slack": _format_slack,
    "discord": _format_discord,
}


async def post_webhook_alert(
    url: str,
    instance_id: int,
    alert_type: str,
    message: str,
    metrics: dict[str, str] | None = None,
    instance: InstanceInfo | None = None,
    format: str = "raw",
    client: httpx.AsyncClient | None = None,
) -> None:
    """POST an alert payload to a webhook URL. Best-effort, never raises."""
    formatter = _FORMATTERS.get(format, _format_raw)
    payload = formatter(instance_id, alert_type, message, metrics, instance)

    try:
        if client is None:
            async with httpx.AsyncClient() as c:
                await c.post(url, json=payload, timeout=10.0)
        else:
            await client.post(url, json=payload, timeout=10.0)
    except Exception:
        pass  # Best effort — never disrupt the app
