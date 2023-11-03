import io
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Type, Union

import docker


@lru_cache(maxsize=1)
def get_docker_client(**kwargs: Any) -> docker.DockerClient:  # type: ignore[name-defined]
    """cached version to retrieve docker client. By default it will use environment
    variables to connect to docker daemon.

    :param kwargs: additional arguments to pass to docker client
    :return: docker client object
    """
    return docker.from_env(**kwargs)  # type: ignore[attr-defined]


def generate_random_container_tag() -> str:
    """Generates a random tag for a docker container.
    Format: ds_pycontain_runner:YYYY-MM-DD-HH-MM-SS-<8 random chars>

    :return: random tag for a docker container.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    return f"ds_pycontain_runner:{timestamp}-{uuid.uuid4().hex[:8]}"


class DockerImage:
    """Represents a locally available docker image as a tag.
    You can either use existing docker image or build a new one from Dockerfile.

    >>> image = DockerImage.from_tag("alpine")
    >>> image = DockerImage.from_tag("python", tag="3.9-slim")
    >>> image = DockerImage.from_dockerfile("example/Dockerfile")
    >>> image = DockerImage.from_dockerfile("path/to/dir_with_Dockerfile/", name="cow")
    """

    def __init__(self, name: str):
        """Note that it does not pull the image from the internet.
        It only represents a tag so it must exist on your system.
        It throws ValueError if docker image by that name does not exist locally.

        :param name: docker image name with tag, e.g. "alpine:latest"
        :raises ValueError: if docker image by that name does not exist locally.
        """
        splitted_name = name.split(":")
        if len(splitted_name) == 1:
            # by default, image has latest tag.
            self.name = name + ":latest"
        else:
            self.name = name

        if not self.exists(name):
            raise ValueError(
                f"Invalid value: name={name} does not exist on your system." "Use DockerImage.from_tag() to pull it."
            )

    def __repr__(self) -> str:
        """String representation of the object.
        :return: string representation of the object (container name)."""
        return f"DockerImage(name={self.name})"

    @classmethod
    def exists(cls, name: str) -> bool:
        """Checks if the docker image exists.
        :param name: docker image name with tag, e.g. "alpine:latest"
        :return: True if docker image exists, False otherwise
        """
        docker_client = get_docker_client()
        return len(docker_client.images.list(name=name)) > 0

    @classmethod
    def remove(cls, name: str) -> None:
        """**WARNING:** Removes image from the system, be cautious with this function.
        It is irreversible operation!.
        :param name: docker image name with tag, e.g. "alpine:latest"
        """
        if cls.exists(name):
            docker_client = get_docker_client()
            docker_client.images.remove(name)

    @classmethod
    def from_tag(
        cls,
        repository: str,
        tag: str = "latest",
        auth_config: Optional[Dict[str, str]] = None,
    ) -> "DockerImage":
        """Use image with a given repository and tag. It is going to pull it if it is
        not present on the system.

        **Examples:**

        >>> repository = "alpine" # (will get "latest" tag)
        >>> repository = "python", tag = "3.9-slim"

        :param repository: docker image repository, e.g. "alpine".
        :param tag: docker image tag, e.g. "latest".
        :param auth_config: authentication configuration for private repositories.
        :return: DockerImage object representing pulled image on the system.
        """
        docker_client = get_docker_client()
        name = f"{repository}:{tag}"
        if len(docker_client.images.list(name=name)) > 0:
            return cls(name=name)
        docker_client.images.pull(repository=repository, tag=tag, auth_config=auth_config)
        return cls(name=name)

    @classmethod
    def from_dockerfile(
        cls,
        dockerfile_path: Union[Path, str],
        name: Union[str, Callable[[], str]] = generate_random_container_tag,
        **kwargs: Any,
    ) -> "DockerImage":
        """Build a new image from Dockerfile given its file path.

        :param dockerfile_path: path to Dockerfile
        :param name: name of the image to build or name generator function
        defaults to generate_random_container_tag()
        :param kwargs: additional arguments to pass to docker client images.build()
        :return: DockerImage object representing built image on the system.
        :raises ValueError: if dockerfile_path is not a valid path to Dockerfile.
        """

        img_name = name if isinstance(name, str) and name else generate_random_container_tag()
        dockerfile = Path(dockerfile_path)

        docker_client = get_docker_client()

        if dockerfile.is_dir():
            if not (dockerfile / "Dockerfile").exists():
                raise ValueError(f"Directory {dockerfile} does not contain a Dockerfile.")
            docker_client.images.build(path=str(dockerfile), tag=img_name, rm=True, **kwargs)
        elif dockerfile.name == "Dockerfile" and dockerfile.is_file():
            with open(dockerfile, "rb") as df:
                docker_client.images.build(fileobj=df, tag=img_name, rm=True, **kwargs)
        else:
            raise ValueError(f"Invalid parameter: dockerfile: {dockerfile}")

        return cls(name=img_name)

    @classmethod
    def from_dockerfile_content(
        cls,
        dockerfile_str: str,
        name: Union[str, Callable[[], str]] = generate_random_container_tag,
        **kwargs: Any,
    ) -> "DockerImage":
        """Build a new image from Dockerfile given a string with Dockerfile content.

        :param dockerfile_str: string with Dockerfile content.
        :param name: name of the image to build or name generator function
        defaults to generate_random_container_tag()
        :param kwargs: additional arguments to pass to docker client images.build()
        :return: DockerImage object representing built image on the system.
        """

        img_name = name if isinstance(name, str) and name else generate_random_container_tag()

        buff = io.BytesIO(dockerfile_str.encode("utf-8"))

        docker_client = get_docker_client()

        docker_client.images.build(fileobj=buff, tag=img_name, rm=True, path=str(Path.cwd()), **kwargs)

        return cls(name=img_name)


class DockerContainer:
    """An isolated environment for running commands, based on docker container.

    **Examples:**

    If you need to run container for a single job:

    >>> container = DockerContainer(DockerImage.from_tag("alpine"))
    >>> status_code, logs = container.spawn_run("echo hello world")

    To run a container in background and execute commands:

    >>> with DockerContainer(DockerImage.from_tag("alpine")) as container:
    >>>     status_code, logs = container.run("echo hello world")
    """

    def __init__(self, image: DockerImage, **kwargs: Any):
        """Wraps docker image to control container interaction.
        NOTE: **kwargs are passed to docker client containers.run() method so you can
        use them as you wish.

        :param image: docker image to use for container
        :param kwargs: additional arguments to pass to docker client containers.run()
        """
        self.image = image
        self._client = get_docker_client()
        self._container = None
        self._run_kwargs = kwargs

    def __enter__(self) -> "DockerContainer":
        """Enters container context. It means that container is started and you can
        execute commands inside it.
        """
        self.unsafe_start()
        return self

    def unsafe_start(self) -> None:
        """Starts container without entering it.
        Please prefer to use with DockerContainer statement.
        """
        assert self._container is None, "You cannot re-entry container"
        # tty=True is required to keep container alive
        self._container = self._client.containers.run(
            self.image.name,
            detach=True,
            tty=True,
            **self._run_kwargs,
        )

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        """Cleanup container on exit.
        :param exc_type: exception type
        :param exc: exception instance (unused)
        :param traceback: traceback object (unused)
        :return: True if exception was handled, False otherwise
        """
        assert self._container is not None, "You cannot exit unstarted container."
        if exc_type is not None:
            # re-throw exception. try to stop container and remove it
            try:
                self._cleanup()
            except Exception as e:  # pylint: disable=broad-except
                print("Failed to stop and remove container to cleanup exception.", e)
            return False
        self.unsafe_exit()
        return True

    def unsafe_exit(self) -> None:
        """Cleanup container on exit. Please prefer to use `with` statement."""
        if self._container is None:
            return
        self._cleanup()
        self._container = None

    def spawn_run(self, command: Union[str, List[str]], **kwargs: Any) -> Tuple[int, bytes]:
        """Run a script in the isolated environment which is docker container with the
        same lifetime as this function call.

        You can also pass all arguments that docker client containers.run() accepts.
        It blocks till command is finished.

        :param command: command to execute in the container
        :param kwargs: additional arguments to pass to docker client containers.run()
        :return: tuple of exit code and logs
        """
        # we can update here kwargs with self._run_kwargs so user can override them
        custom_kwargs = self._run_kwargs.copy().update(kwargs) if kwargs else self._run_kwargs
        # There is a known issue with auto_remove=True and docker-py:
        # https://github.com/docker/docker-py/issues/1813
        # so as workaround we detach, wait & and remove container manually
        container = self._client.containers.run(self.image.name, command=command, detach=True, **custom_kwargs)
        status_code = container.wait().get("StatusCode", 1)
        logs = container.logs()
        container.remove()
        return status_code, logs

    @property
    def docker_container(self) -> docker.models.containers.Container:  # type: ignore[name-defined]
        """Returns docker container object.
        :return: docker container object"""
        assert self._container is not None, "You cannot access container that was not entered"
        return self._container

    @property
    def name(self) -> str:
        """Name of the container if it exists, empty string otherwise.
        :return: container name as string."""
        if self._container:
            return self._container.name
        return ""

    def run(
        self, command: Union[str, List[str]], **kwargs: Any
    ) -> Tuple[int, Union[bytes, Tuple[bytes, bytes], Generator[bytes, None, None]]]:
        """Run a script in the isolated environment which is docker container.
        You can send any args which docker-py exec_run accepts:
        https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.Container.exec_run
        Return is a tuple of exit code and output which is controlled by arguments:
        stream, socket and demux.

        :param command: command to execute in the container
        :param kwargs: additional arguments to pass to docker client containers.run()
        :return: tuple of exit code and output (stream, socket or demux)
        """
        assert self._container is not None, "You cannot execute command in container that was not entered"

        exit_code, output = self._container.exec_run(cmd=command, **kwargs)
        return exit_code, output

    def _cleanup(self) -> None:
        """Stops and removes container."""
        if self._container is None:
            return
        self._container.stop()
        self._container.remove()
