import json
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional

import requests

from ds_pycontain.docker_containers import DockerContainer, DockerImage


def _get_dockerfile_content(base_image: str, script_path: str) -> str:
    """Generates on the fly dockerfile for python runner.
    It is used to build docker image for python REPL server.

    :param base_image: base image to use for the docker image.
    :param script_path: path to python_docker_repl_runner.py script.
    :return: dockerfile content as string.
    """
    return f"""FROM {base_image}
RUN pip install --no-cache-dir pydantic==1.10.12

RUN adduser -D runner
USER runner

WORKDIR /app

COPY {script_path} /app/python_runner.py
# Ensure python output is not buffered to remove logs delay
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["python3", "/app/python_runner.py"]
"""


def _build_or_use_docker_image(
    base_image: str = "python:3.11-alpine3.18",
) -> DockerImage:
    """Builds docker image from data/python_runner.py script
    and docker template.

    :param base_image: base image to use for the docker image.
    :return: docker image.
    """

    # we autogenerate deterministic name for the image
    name = f"ds_pycontain_pyrepl_{base_image}"
    script_name = "python_runner.py"
    # workaround for https://github.com/docker/docker-py/issues/2105
    # which fails to use in-memory dockerfile with passing docker build
    # context. It requires to pass directory name.
    with TemporaryDirectory() as tmpdir:
        runner_script = Path(__file__).parent / "data" / script_name
        assert runner_script.exists()
        shutil.copy(runner_script, tmpdir)
        dockerfile_content = _get_dockerfile_content(base_image, script_name)
        dockerfile = Path(tmpdir) / "Dockerfile"
        with dockerfile.open("w") as f:
            f.write(dockerfile_content)
        return DockerImage.from_dockerfile(dockerfile.parent, name=name)


class PythonContainerREPL:
    """This class is a wrapper around the docker container that runs the python
    REPL server. It is used to execute python code in the container and return
    the results.

    It assumes specific docker image is used which runs langchain python runner
    server and it communicates by HTTP requests."""

    def __init__(
        self,
        port: int = 7123,
        image: Optional[DockerImage] = None,
        base_image: str = "python:3.11-alpine3.18",
        **kwargs: Dict[str, Any],
    ) -> None:
        """Starts docker container with python REPL server and wait till it
        gets operational.

        If image is not provided it will build based on
        the base_image and python_docker_repl_runner.py script.

        All other params: **kwargs are passed to DockerContainer constructor,
        however port mapping is hardcoded to map docker's 8080 to provided port.
        You can use it to limit memory/cpu etc. of the container.

        :param port: port to use for the python REPL server.
        :param image: docker image to use for the container.
        :param base_image: base image to use for the docker image.
        :param kwargs: additional params to pass to DockerContainer constructor.
        """
        # for now use the image we created.
        self.port = port
        if image is None and not base_image:
            raise ValueError("Either image or base_image must be provided.")
        self.image = image if image is not None else _build_or_use_docker_image(base_image)
        self.container = DockerContainer(self.image, ports={"8080/tcp": port}, **kwargs)
        # we need to start non-lexical scope lifetime for container
        # usually with statement should be used.
        # __del__ will close container.
        self.container.unsafe_start()
        self.session = requests.Session()
        # we need to ensure container is running and REPL server is
        # ready to accept requests, otherwise we might get connection
        # refused due to race conditions.
        self._wait_for_container_running()
        self._wait_for_repl_ready()

    def _wait_for_container_running(self, timeout: float = 3.0) -> None:
        """Sleep until container is running or timeout is reached.

        :param timeout: timeout in seconds.
        :raises TimeoutError: if timeout is reached.
        """
        status = self.container.docker_container.status
        while status not in ("created", "running"):
            time.sleep(0.1)
            timeout -= 0.1
            if timeout < 0:
                raise TimeoutError(f"Failed to start container - status={status}")

    def _wait_for_repl_ready(self, timeout: float = 3.0) -> None:
        """Sleep until REPL server is ready to accept requests or timeout is reached.

        :param timeout: timeout in seconds.
        :raises TimeoutError: if timeout is reached."""
        while True:
            try:
                banner = self.session.get(f"http://localhost:{self.port}")
                if banner.text != "Hello! I am a python REPL server.":
                    raise ValueError("Unrecognized banner, it is not a langchain python REPL server.")
                break
            except Exception as ex:  # pylint: disable=broad-except
                time.sleep(0.1)
                timeout -= 0.1
                if timeout < 0:
                    raise TimeoutError("Failed to boot service. Timed out.") from ex

    def __del__(self) -> None:
        """Closes container and removes it."""
        self.container.unsafe_exit()

    def _exec(self, code: str, use_ast: bool = True) -> str:
        """Executes code and returns captured stdout. or error message.

        :param code: code to execute.
        :param use_ast: if True, use ast module to parse code, otherwise use eval.
        :return: stdout or error message.
        """
        try:
            msg = {"code": code, "use_ast": 1 if use_ast else 0}
            result = self.session.post(f"http://localhost:{self.port}", json=msg)
        except Exception as ex:  # pylint: disable=broad-except
            return repr(ex.with_traceback(None))
        data = result.text
        if not data:
            return ""
        output = json.loads(data)
        return output.get("result", "")

    def eval(self, code: str) -> str:
        """Evaluate code and return result as string.

        :param code: code to evaluate.
        :return: result as string.
        """
        return self._exec(code, use_ast=True)

    def exec(self, code: str) -> str:
        """Execute code and return stdout.

        :param code: code to execute.
        :return: result as string.
        """
        return self._exec(code, use_ast=False)

    def run(self, command: str, timeout: Optional[int] = None) -> str:
        """Run command and returns anything printed.
        Timeout, if provided, is not currently supported and will be ignored.

        :param command: command to run.
        :param timeout: timeout in seconds.
        :return: result from REPL as output.
        """

        # potentially add a warning or log message if a timeout is provided,
        # as it's not supported in the current implementation.
        if timeout is not None:
            print("Warning: timeout is not supported in the current implementation.")

        # exec method is used here as it will execute the command and return stdout.
        return self.exec(command)
