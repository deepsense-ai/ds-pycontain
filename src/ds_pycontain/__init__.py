""" ds_pycontain is a Python package for managing Docker containers and images. """
from .__version__ import __version__
from .docker_containers import DockerContainer, DockerImage, generate_random_container_tag, get_docker_client

__all__ = ["__version__", "DockerContainer", "DockerImage", "generate_random_container_tag", "get_docker_client"]
