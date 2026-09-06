import os
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple


CPP_DOCKER_IMAGE = os.environ.get(
    "LIVE_EDITOR_CPP_DOCKER_IMAGE",
    "wifi-codeshare-cpp-runner:1.0",
)
CPP_DOCKER_MEMORY = os.environ.get("LIVE_EDITOR_CPP_DOCKER_MEMORY", "512m")
CPP_DOCKER_CPUS = os.environ.get("LIVE_EDITOR_CPP_DOCKER_CPUS", "1.0")
CPP_DOCKER_PIDS = os.environ.get("LIVE_EDITOR_CPP_DOCKER_PIDS", "64")
CPP_DOCKER_WORKSPACE_SIZE = os.environ.get(
    "LIVE_EDITOR_CPP_DOCKER_WORKSPACE_SIZE",
    "128m",
)
CPP_READY_MARKER = "__WIFI_CODESHARE_CPP_READY__"
CPP_CONTAINER_LABEL = "wifi-codeshare.execution=cpp"
MAX_CAPTURE_OUTPUT_CHARS = 100_000


class DockerExecutionError(RuntimeError):
    """Raised when the restricted Docker runner cannot be started safely."""


def resolve_docker_executable() -> Optional[str]:
    configured = os.environ.get("LIVE_EDITOR_DOCKER_EXECUTABLE", "").strip()
    if configured:
        if os.path.isfile(configured):
            return configured
        resolved = shutil.which(configured)
        if resolved:
            return resolved

    resolved = shutil.which("docker")
    if resolved:
        return resolved

    if os.name == "nt":
        candidates = [
            os.path.join(
                os.environ.get("ProgramFiles", r"C:\Program Files"),
                "Docker",
                "Docker",
                "resources",
                "bin",
                "docker.exe",
            ),
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Programs",
                "Docker",
                "Docker",
                "resources",
                "bin",
                "docker.exe",
            ),
        ]
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
    return None


def _run_docker_check(arguments: List[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    docker = resolve_docker_executable()
    if not docker:
        raise DockerExecutionError(
            "Docker was not found. Install and start Docker Desktop, then restart CMD."
        )
    try:
        return subprocess.run(
            [docker, *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DockerExecutionError(
            "Docker Desktop did not respond. Start Docker Desktop and wait for the engine."
        ) from exc


def ensure_cpp_docker_ready() -> str:
    info = _run_docker_check(["info", "--format", "{{.OSType}}"])
    if info.returncode != 0:
        detail = (info.stderr or info.stdout).strip()
        raise DockerExecutionError(
            detail
            or "Docker Desktop is not running. Start it and wait for the Linux engine."
        )
    if info.stdout.strip().lower() != "linux":
        raise DockerExecutionError(
            "The C++ runner requires Docker Desktop in Linux-container mode."
        )

    image = _run_docker_check(["image", "inspect", CPP_DOCKER_IMAGE])
    if image.returncode != 0:
        raise DockerExecutionError(
            f"Docker image '{CPP_DOCKER_IMAGE}' is missing. Run setup-docker.cmd once."
        )
    docker = resolve_docker_executable()
    if not docker:
        raise DockerExecutionError("Docker became unavailable while preparing the C++ runner.")
    return docker


def create_container_name() -> str:
    return f"wifi-codeshare-cpp-{uuid.uuid4().hex[:20]}"


def build_cpp_docker_command(
    docker: str,
    source_directory: str,
    container_name: str,
    execution_seconds: float = 60.0,
) -> List[str]:
    source_directory = os.path.abspath(source_directory)
    return [
        docker,
        "run",
        "--rm",
        "--interactive",
        "--pull=never",
        "--name",
        container_name,
        "--label",
        CPP_CONTAINER_LABEL,
        "--init",
        "--restart",
        "no",
        "--network",
        "none",
        "--ipc",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--memory",
        CPP_DOCKER_MEMORY,
        "--memory-swap",
        CPP_DOCKER_MEMORY,
        "--cpus",
        CPP_DOCKER_CPUS,
        "--pids-limit",
        CPP_DOCKER_PIDS,
        "--ulimit",
        "nofile=256:256",
        "--tmpfs",
        (
            "/workspace:rw,nosuid,nodev,exec,uid=10001,gid=10001,mode=0770,"
            f"size={CPP_DOCKER_WORKSPACE_SIZE}"
        ),
        "--mount",
        f"type=bind,source={source_directory},target=/source,readonly",
        "--env",
        "HOME=/workspace",
        "--env",
        "TMPDIR=/workspace",
        "--env",
        f"LIVE_EDITOR_EXECUTION_TIMEOUT={max(1.0, float(execution_seconds)):g}",
        "--workdir",
        "/workspace",
        "--user",
        "10001:10001",
        CPP_DOCKER_IMAGE,
    ]


def remove_cpp_container(container_name: Optional[str]) -> None:
    if not container_name:
        return
    docker = resolve_docker_executable()
    if not docker:
        return
    try:
        subprocess.run(
            [docker, "rm", "--force", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def remove_ready_marker(stderr: str) -> Tuple[str, bool]:
    marker_line = f"{CPP_READY_MARKER}\n"
    if marker_line in stderr:
        return stderr.replace(marker_line, "", 1), True
    if stderr.rstrip("\r\n") == CPP_READY_MARKER:
        return "", True
    return stderr, False


def run_cpp_in_docker(code: str, stdin: str, timeout: float) -> Dict[str, Any]:
    docker = ensure_cpp_docker_ready()
    container_name = create_container_name()
    with tempfile.TemporaryDirectory(prefix="wifi_codeshare_cpp_") as temp_dir:
        source_path = os.path.join(temp_dir, "main.cpp")
        with open(source_path, "w", encoding="utf-8", newline="\n") as source_file:
            source_file.write(code)
        command = build_cpp_docker_command(
            docker,
            temp_dir,
            container_name,
            execution_seconds=timeout,
        )
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=stdout_file,
                    stderr=stderr_file,
                )
            except OSError as exc:
                raise DockerExecutionError(
                    "Docker could not start the restricted C++ container."
                ) from exc
            try:
                if process.stdin:
                    process.stdin.write(stdin.encode("utf-8"))
                    process.stdin.close()
                deadline = time.monotonic() + timeout + 20.0
                output_limited = False
                while process.poll() is None:
                    output_size = (
                        os.fstat(stdout_file.fileno()).st_size
                        + os.fstat(stderr_file.fileno()).st_size
                    )
                    if output_size > MAX_CAPTURE_OUTPUT_CHARS:
                        output_limited = True
                        remove_cpp_container(container_name)
                        break
                    if time.monotonic() >= deadline:
                        remove_cpp_container(container_name)
                        try:
                            process.kill()
                        except OSError:
                            pass
                        process.wait(timeout=5)
                        raise subprocess.TimeoutExpired(command, timeout + 20.0)
                    time.sleep(0.02)

                if process.poll() is None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except OSError:
                            pass
                        process.wait(timeout=5)

                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout = stdout_file.read(MAX_CAPTURE_OUTPUT_CHARS + 1).decode(
                    "utf-8",
                    errors="replace",
                )
                stderr = stderr_file.read(MAX_CAPTURE_OUTPUT_CHARS + 1).decode(
                    "utf-8",
                    errors="replace",
                )
            finally:
                if process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        pass
                remove_cpp_container(container_name)

    stderr, program_started = remove_ready_marker(stderr)
    remaining = MAX_CAPTURE_OUTPUT_CHARS
    visible_stdout = stdout[:remaining]
    remaining -= len(visible_stdout)
    visible_stderr = stderr[:remaining]
    if len(stdout) + len(stderr) > MAX_CAPTURE_OUTPUT_CHARS:
        output_limited = True
    if output_limited:
        if visible_stderr and not visible_stderr.endswith("\n"):
            visible_stderr += "\n"
        visible_stderr += (
            f"Output stopped after {MAX_CAPTURE_OUTPUT_CHARS:,} characters."
        )
    return {
        "stdout": visible_stdout,
        "stderr": visible_stderr,
        "returncode": -1 if output_limited else process.returncode,
        "stage": "run" if program_started else "compile",
        "output_limited": output_limited,
    }
