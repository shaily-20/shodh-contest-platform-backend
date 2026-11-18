import base64
import time

import docker
from docker.errors import DockerException, ImageNotFound

from app.config import settings

WRAPPER = (
    "import base64,io,os,sys;"
    "source=base64.b64decode(os.environ['SHODH_SOURCE']).decode('utf-8');"
    "data=base64.b64decode(os.environ['SHODH_INPUT']).decode('utf-8');"
    "sys.stdin=io.StringIO(data);"
    "exec(compile(source,'<submission>','exec'),{'__name__':'__main__'})"
)
MAX_OUTPUT_BYTES = 64 * 1024


class RunnerInfrastructureError(Exception):
    pass


def run_python(code: str, test_input: str) -> tuple[str, str, float, bool]:
    """Run one case in a fresh, tightly constrained local Docker container."""
    try:
        client = docker.from_env(timeout=settings.runner_timeout_seconds + 10)
        try:
            try:
                client.images.get(settings.runner_image)
            except ImageNotFound:
                client.images.pull(settings.runner_image)
            started = time.monotonic()
            container = client.containers.run(
                settings.runner_image,
                command=["python", "-I", "-c", WRAPPER],
                environment={
                    "SHODH_SOURCE": base64.b64encode(code.encode()).decode("ascii"),
                    "SHODH_INPUT": base64.b64encode(test_input.encode()).decode("ascii"),
                },
                detach=True,
                network_disabled=True,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
                mem_limit=settings.runner_memory_bytes,
                nano_cpus=1_000_000_000,
                pids_limit=32,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                user="65534:65534",
                working_dir="/tmp",
                stdout=True,
                stderr=True,
                auto_remove=False,
            )
            timed_out = False
            try:
                try:
                    result = container.wait(timeout=settings.runner_timeout_seconds)
                except Exception as exc:
                    # Docker SDK raises a timeout exception; stop this case before reading output.
                    if "timeout" not in type(exc).__name__.lower() and "timeout" not in str(exc).lower():
                        raise
                    timed_out = True
                    container.kill()
                    result = {"StatusCode": 124}
                logs = container.logs(stdout=True, stderr=True)[: MAX_OUTPUT_BYTES + 1]
                elapsed = time.monotonic() - started
                output = logs.decode("utf-8", errors="replace")
                excessive = len(logs) > MAX_OUTPUT_BYTES
                if excessive:
                    output = output[:MAX_OUTPUT_BYTES]
                return output, "", elapsed, timed_out or excessive or result.get("StatusCode") == 124
            finally:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass
        finally:
            client.close()
    except DockerException as exc:
        raise RunnerInfrastructureError("Docker execution failed") from exc
