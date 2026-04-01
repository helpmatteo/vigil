from __future__ import annotations

import asyncio
import math
import random

from .discovery import InstanceInfo
from .parser import MetricParser
from .widgets.instance_panel import InstancePanel

VAST_DEMO_INSTANCES: list[InstanceInfo] = [
    InstanceInfo(
        id=814209,
        ssh_host="209.20.158.98",
        ssh_port=22340,
        gpu_name="RTX 4090",
        num_gpus=1,
        status="running",
        machine_id=18042,
        label="dreamerv3-atari",
        dph_total=0.362,
    ),
    InstanceInfo(
        id=814371,
        ssh_host="64.247.196.60",
        ssh_port=22091,
        gpu_name="A100 80GB",
        num_gpus=2,
        status="running",
        machine_id=21587,
        label="llama3-finetune",
        dph_total=0.524,
    ),
    InstanceInfo(
        id=814502,
        ssh_host="173.212.230.115",
        ssh_port=22178,
        gpu_name="RTX 3090",
        num_gpus=1,
        status="running",
        machine_id=9831,
        label="resnet-imgnet",
        dph_total=0.196,
    ),
    InstanceInfo(
        id=814688,
        ssh_host="45.79.112.44",
        ssh_port=22455,
        gpu_name="H100 SXM",
        num_gpus=4,
        status="running",
        machine_id=30215,
        label="moe-pretrain",
        dph_total=0.202,
    ),
]

RUNPOD_DEMO_INSTANCES: list[InstanceInfo] = [
    InstanceInfo(
        id="rp-7k3m9x2n",
        ssh_host="194.68.245.17",
        ssh_port=21022,
        gpu_name="A6000",
        num_gpus=2,
        status="RUNNING",
        machine_id=0,
        label="gpt2-distill",
        dph_total=0.440,
    ),
    InstanceInfo(
        id="rp-4w8j5p1q",
        ssh_host="82.156.91.203",
        ssh_port=21044,
        gpu_name="RTX 4080",
        num_gpus=1,
        status="RUNNING",
        machine_id=0,
        label="sd-lora-train",
        dph_total=0.280,
    ),
]

DEMO_INSTANCES = VAST_DEMO_INSTANCES + RUNPOD_DEMO_INSTANCES

VAST_DEMO_CREDIT = 47.82
RUNPOD_DEMO_CREDIT = 32.15
DEMO_CREDIT = VAST_DEMO_CREDIT + RUNPOD_DEMO_CREDIT
DEMO_TOTAL_DPH = sum(i.dph_total for i in DEMO_INSTANCES)


async def demo_stream_dreamerv3(panel: InstancePanel, parser: MetricParser) -> None:
    panel.set_status("connected")
    step = 14800
    reward = 2.1
    policy_loss = 0.112
    value_loss = 0.38
    fps = 820.0

    while True:
        step += random.randint(50, 200)
        reward += random.uniform(-0.15, 0.25)
        reward = max(0.5, reward)
        policy_loss *= random.uniform(0.985, 1.005)
        policy_loss = max(0.01, policy_loss)
        value_loss *= random.uniform(0.988, 1.004)
        value_loss = max(0.05, value_loss)
        fps = 820 + random.uniform(-40, 40)

        line = (
            f"step: {step} | reward: {reward:.2f} | "
            f"policy_loss: {policy_loss:.4f} | value_loss: {value_loss:.3f} | fps: {fps:.0f}"
        )
        metrics = parser.parse_line(line)
        panel.add_log_line(line, metrics)
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def demo_stream_hf_finetune(panel: InstancePanel, parser: MetricParser) -> None:
    panel.set_status("connected")
    step = 0
    total_steps = 12000
    loss = 1.82
    lr = 2e-5
    epoch = 0.0

    while True:
        step += random.randint(8, 20)
        if step > total_steps:
            step = total_steps
        epoch = step / 800.0
        loss *= random.uniform(0.992, 1.003)
        loss = max(0.15, loss)
        # cosine lr decay
        lr = 2e-5 * 0.5 * (1 + math.cos(math.pi * step / total_steps))
        eval_loss = loss * random.uniform(0.85, 1.1)

        if step % 100 < 20:
            line = (
                f"[Epoch {epoch:.2f}] step: {step}/{total_steps} | "
                f"loss: {loss:.4f} | eval_loss: {eval_loss:.4f} | lr: {lr:.2e}"
            )
        else:
            line = (
                f"[Epoch {epoch:.2f}] step: {step}/{total_steps} | "
                f"loss: {loss:.4f} | lr: {lr:.2e}"
            )
        metrics = parser.parse_line(line)
        panel.add_log_line(line, metrics)
        await asyncio.sleep(random.uniform(0.25, 0.6))

        if step >= total_steps:
            step = 0
            loss = 1.82


async def demo_stream_plateau(panel: InstancePanel, parser: MetricParser) -> None:
    panel.set_status("connected")
    epoch = 1
    val_loss = 0.62
    train_loss = 0.65
    val_acc = 0.768

    while True:
        epoch += 1
        # Converge toward a plateau
        if epoch < 10:
            val_loss *= random.uniform(0.96, 0.995)
            train_loss *= random.uniform(0.955, 0.99)
            val_acc += random.uniform(0.005, 0.015)
        else:
            # Plateau: tiny fluctuations
            val_loss += random.uniform(-0.0003, 0.0003)
            train_loss += random.uniform(-0.0005, 0.0005)
            val_acc += random.uniform(-0.001, 0.001)

        val_acc = min(val_acc, 0.999)
        line = (
            f"Epoch {epoch} | val_loss: {val_loss:.4f} | "
            f"train_loss: {train_loss:.4f} | accuracy: {val_acc:.3f}"
        )
        metrics = parser.parse_line(line)
        panel.add_log_line(line, metrics)
        await asyncio.sleep(random.uniform(0.3, 0.6))


async def demo_stream_custom(panel: InstancePanel, parser: MetricParser) -> None:
    panel.set_status("connected")
    step = 8000
    loss = 0.085
    lr = 1.5e-4
    accuracy = 0.912
    total_steps = 50000

    while True:
        step += random.randint(100, 400)
        loss *= random.uniform(0.990, 1.004)
        loss = max(0.005, loss)
        # cosine lr
        lr = 1.5e-4 * 0.5 * (1 + math.cos(math.pi * step / total_steps))
        accuracy += random.uniform(-0.002, 0.006)
        accuracy = min(accuracy, 0.999)

        line = f"[step {step}] loss={loss:.4f} lr={lr:.2e} accuracy={accuracy:.3f}"
        metrics = parser.parse_line(line)
        panel.add_log_line(line, metrics)
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def demo_stream_distill(panel: InstancePanel, parser: MetricParser) -> None:
    panel.set_status("connected")
    step = 4200
    loss = 2.341
    lr = 5.0e-5
    accuracy = 0.412

    while True:
        step += random.randint(10, 40)
        loss *= random.uniform(0.993, 1.003)
        loss = max(0.8, loss)
        lr = 5.0e-5 * random.uniform(0.98, 1.02)
        accuracy += random.uniform(-0.003, 0.008)
        accuracy = min(accuracy, 0.95)

        line = f"step: {step} | loss: {loss:.3f} | lr: {lr:.1e} | accuracy: {accuracy:.3f}"
        metrics = parser.parse_line(line)
        panel.add_log_line(line, metrics)
        await asyncio.sleep(random.uniform(0.25, 0.55))


async def demo_stream_sd_lora(panel: InstancePanel, parser: MetricParser) -> None:
    panel.set_status("connected")
    step = 1500
    loss = 0.0821
    epoch = 3.42

    while True:
        step += random.randint(5, 15)
        loss *= random.uniform(0.994, 1.004)
        loss = max(0.02, loss)
        epoch += random.uniform(0.01, 0.03)

        line = f"[step {step}] loss={loss:.4f} epoch={epoch:.2f}"
        metrics = parser.parse_line(line)
        panel.add_log_line(line, metrics)
        await asyncio.sleep(random.uniform(0.2, 0.5))


VAST_DEMO_STREAMS = [
    demo_stream_dreamerv3,
    demo_stream_hf_finetune,
    demo_stream_plateau,
    demo_stream_custom,
]

RUNPOD_DEMO_STREAMS = [
    demo_stream_distill,
    demo_stream_sd_lora,
]

DEMO_STREAMS = VAST_DEMO_STREAMS + RUNPOD_DEMO_STREAMS
