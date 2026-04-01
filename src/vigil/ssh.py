from __future__ import annotations

import asyncssh

from .config import Config
from .discovery import InstanceInfo


async def ssh_connect(
    instance: InstanceInfo,
    config: Config,
    *,
    keepalive: bool = True,
) -> asyncssh.SSHClientConnection:
    """Open an SSH connection to a Vast.ai instance.

    Args:
        instance: The instance to connect to.
        config: App configuration (provides ssh_key_path).
        keepalive: Whether to enable SSH keepalive (disable for one-shot commands).
    """
    kwargs: dict = dict(
        host=instance.ssh_host,
        port=instance.ssh_port,
        username=config.ssh_username_for(instance.id),
        client_keys=[str(config.ssh_key_path)],
        known_hosts=None,  # Vast.ai instances are ephemeral — host keys change on every recreate
        login_timeout=config.ssh_login_timeout,
    )
    if keepalive:
        kwargs["keepalive_interval"] = config.ssh_keepalive_interval
        kwargs["keepalive_count_max"] = 3

    return await asyncssh.connect(**kwargs)
