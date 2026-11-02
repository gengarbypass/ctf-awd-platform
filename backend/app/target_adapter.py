import asyncio
import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import httpx
from docker.types import IPAMConfig, IPAMPool

from .config import settings
from .models import Service, Target
from .security import derive_terminal_password


@dataclass
class HealthResult:
    ok: bool
    error: str = ""


class TargetAdapter(ABC):
    @abstractmethod
    async def initialize_target(self, target: Target, service: Service, team_no: int) -> None: ...

    @abstractmethod
    async def start(self, target: Target) -> None: ...

    @abstractmethod
    async def stop(self, target: Target) -> None: ...

    @abstractmethod
    async def restart(self, target: Target) -> None: ...

    @abstractmethod
    async def inject_flag(self, target: Target, service: Service, plaintext_flag: str) -> None: ...

    @abstractmethod
    async def check_health(self, target: Target, service: Service) -> HealthResult: ...

    @abstractmethod
    async def pull_image(self, image: str) -> None: ...

    @abstractmethod
    async def destroy(self, target: Target) -> None: ...


class MockTargetAdapter(TargetAdapter):
    """Explicit development adapter backed by isolated local directories."""

    def __init__(self):
        self.root = Path(settings.mock_target_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._running: set[str] = set()

    def _flag_file(self, target: Target, service: Service) -> Path:
        volume = (self.root / target.volume_name).resolve()
        relative = service.flag_path.lstrip("/")
        path = (volume / relative).resolve()
        if volume != path and volume not in path.parents:
            raise ValueError("flag path escapes target volume")
        return path

    async def initialize_target(self, target, service, team_no) -> None:
        (self.root / target.volume_name).mkdir(parents=True, exist_ok=True)

    async def start(self, target) -> None:
        self._running.add(target.id)

    async def stop(self, target) -> None:
        self._running.discard(target.id)

    async def restart(self, target) -> None:
        self._running.add(target.id)

    async def inject_flag(self, target, service, plaintext_flag) -> None:
        if target.id not in self._running:
            raise RuntimeError("mock target is not running")
        path = self._flag_file(target, service)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{asyncio.get_running_loop().time()}")
        temporary.write_text(plaintext_flag, encoding="utf-8")
        os.replace(temporary, path)
        content = path.read_text(encoding="utf-8")
        if hashlib.sha256(content.encode()).hexdigest() != hashlib.sha256(plaintext_flag.encode()).hexdigest():
            raise RuntimeError("flag readback hash mismatch")

    async def check_health(self, target, service) -> HealthResult:
        if target.id not in self._running:
            return HealthResult(False, "mock target is stopped")
        return HealthResult(True)

    async def pull_image(self, image: str) -> None:
        return None

    async def destroy(self, target) -> None:
        self._running.discard(target.id)
        volume = (self.root / target.volume_name).resolve()
        if volume != self.root and self.root in volume.parents:
            shutil.rmtree(volume, ignore_errors=True)


class DockerTargetAdapter(TargetAdapter):
    def __init__(self):
        import docker

        self._docker = docker.from_env()
        self._not_found = docker.errors.NotFound

    async def initialize_target(self, target, service, team_no) -> None:
        await asyncio.to_thread(self._initialize_target, target, service, team_no)

    def _initialize_target(self, target, service, team_no) -> None:
        self._ensure_image(service.image)
        try:
            self._docker.volumes.get(target.volume_name)
        except self._not_found:
            self._docker.volumes.create(name=target.volume_name, labels={"awd.team": str(team_no)})
        management = self._ensure_network(f"awd-team-{team_no:02d}", f"172.32.{team_no}.0/24")
        attack = self._ensure_network("awd-attack", "172.31.0.0/16")
        self._connect_core_services(attack, ("api", "worker"))
        self._ensure_gateway(team_no, management.name, target.team_id)
        self._connect_core_services(management, ("terminal",))
        try:
            self._docker.containers.get(target.container_name)
            return
        except self._not_found:
            pass
        container = self._docker.containers.create(
            image=service.image,
            name=target.container_name,
            detach=True,
            network=management.name,
            volumes={target.volume_name: {"bind": "/data", "mode": "rw"}},
            ports={f"{service.internal_port}/tcp": target.public_port},
            privileged=False,
            mem_limit="1g",
            nano_cpus=1_000_000_000,
            pids_limit=256,
            security_opt=["no-new-privileges"],
            restart_policy={"Name": "unless-stopped"},
            labels={"awd.team": str(team_no), "awd.service": service.code},
        )
        attack.connect(container, ipv4_address=target.attack_ip)

    def _ensure_image(self, image: str) -> None:
        try:
            self._docker.images.get(image)
        except self._not_found:
            self._docker.images.pull(image)

    async def pull_image(self, image: str) -> None:
        await asyncio.to_thread(self._ensure_image, image)

    def _ensure_network(self, name: str, subnet: str):
        try:
            return self._docker.networks.get(name)
        except self._not_found:
            pool = IPAMPool(subnet=subnet)
            config = IPAMConfig(pool_configs=[pool])
            return self._docker.networks.create(name=name, driver="bridge", ipam=config, internal=False)

    def _connect_core_services(self, network, service_names: tuple[str, ...]) -> None:
        for service_name in service_names:
            containers = self._docker.containers.list(filters={"label": f"com.docker.compose.service={service_name}"})
            for container in containers:
                try:
                    network.connect(container)
                except Exception as exc:
                    if "already exists" not in str(exc).lower():
                        raise

    def _ensure_gateway(self, team_no: int, network: str, team_id: str) -> None:
        name = f"gateway-t{team_no:02d}"
        try:
            self._docker.containers.get(name)
            return
        except self._not_found:
            pass
        self._ensure_image(settings.gateway_image)
        self._docker.containers.create(
            image=settings.gateway_image,
            name=name,
            detach=True,
            network=network,
            environment={
                "USER_NAME": settings.terminal_ssh_username,
                "PASSWORD_ACCESS": "true",
                "USER_PASSWORD": derive_terminal_password(team_id),
            },
            restart_policy={"Name": "unless-stopped"},
            privileged=False,
            mem_limit="256m",
            nano_cpus=250_000_000,
            pids_limit=128,
            security_opt=["no-new-privileges"],
            labels={"awd.team": str(team_no), "awd.gateway": "true"},
        )

    def _container(self, name: str):
        return self._docker.containers.get(name)

    async def start(self, target) -> None:
        gateway = await asyncio.to_thread(self._container, target.gateway_host)
        if gateway.status != "running":
            await asyncio.to_thread(gateway.start)
        container = await asyncio.to_thread(self._container, target.container_name)
        await asyncio.to_thread(container.start)

    async def stop(self, target) -> None:
        container = await asyncio.to_thread(self._container, target.container_name)
        await asyncio.to_thread(container.stop)

    async def restart(self, target) -> None:
        container = await asyncio.to_thread(self._container, target.container_name)
        await asyncio.to_thread(container.restart, 10)

    async def destroy(self, target) -> None:
        await asyncio.to_thread(self._destroy_target, target)

    def _destroy_target(self, target) -> None:
        try:
            container = self._docker.containers.get(target.container_name)
            container.remove(force=True, v=False)
        except self._not_found:
            pass
        try:
            volume = self._docker.volumes.get(target.volume_name)
            volume.remove(force=True)
        except self._not_found:
            pass

    async def inject_flag(self, target, service, plaintext_flag) -> None:
        container = await asyncio.to_thread(self._container, target.container_name)
        directory = os.path.dirname(service.flag_path) or "/"
        command = (
            'mkdir -p "$FLAG_DIR" && tmp="${FLAG_PATH}.tmp.$$" && '
            'printf "%s" "$FLAG_VALUE" > "$tmp" && mv "$tmp" "$FLAG_PATH" && cat "$FLAG_PATH"'
        )
        result = await asyncio.to_thread(
            container.exec_run,
            ["/bin/sh", "-c", command],
            environment={
                "FLAG_DIR": directory,
                "FLAG_PATH": service.flag_path,
                "FLAG_VALUE": plaintext_flag,
            },
            demux=True,
        )
        if result.exit_code != 0:
            stderr = (result.output[1] or b"").decode(errors="replace")
            raise RuntimeError(f"flag injection failed: {stderr[:500]}")
        stdout = (result.output[0] or b"").decode()
        if hashlib.sha256(stdout.encode()).hexdigest() != hashlib.sha256(plaintext_flag.encode()).hexdigest():
            raise RuntimeError("flag readback hash mismatch")

    async def check_health(self, target, service) -> HealthResult:
        try:
            if service.protocol == "HTTP":
                scheme = service.check_config.get("scheme", "http")
                path = service.check_config.get("path", "/")
                expected = int(service.check_config.get("status", 200))
                url = f"{scheme}://{target.attack_ip}:{service.internal_port}{path}"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                if response.status_code != expected:
                    return HealthResult(False, f"unexpected HTTP status {response.status_code}")
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target.attack_ip, service.internal_port), timeout=5.0
                )
                command = service.check_config.get("command")
                if command:
                    writer.write(str(command).encode())
                    await writer.drain()
                    response = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                    expected = str(service.check_config.get("contains", "")).encode()
                    if expected and expected not in response:
                        return HealthResult(False, "protocol response did not contain expected text")
                writer.close()
                await writer.wait_closed()
            return HealthResult(True)
        except (OSError, httpx.HTTPError, asyncio.TimeoutError) as exc:
            return HealthResult(False, str(exc)[:500])


def create_target_adapter() -> TargetAdapter:
    if settings.allow_mock_docker:
        if settings.environment == "production":
            raise RuntimeError("mock Docker adapter is forbidden in production")
        return MockTargetAdapter()
    return DockerTargetAdapter()
