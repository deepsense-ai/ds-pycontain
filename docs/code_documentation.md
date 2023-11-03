# Code documentation

**ds_pycontain** is a python package which provides an abstraction over the docker API.

Supported functionality covers:
- Building docker images from Dockerfiles
- Pulling docker images from dockerhub (or similar)
- Running docker containers to execute a one-off command
- Running docker containers to execute a long-running process and communicate with it


```python
  from ds_pycontain import DockerContainer, DockerImage, get_docker_client

  client = get_docker_client()

  # This will fetch the image from dockerhub if it is not already present
  # with the "latest" tag. Then container is started and commands are run
  with DockerContainer(DockerImage.from_tag("alpine")) as container:
      ret_code, output = container.run("touch /animal.txt")
      assert ret_code == 0

      ret_code, output = container.run("ls /")
      assert ret_code == 0
      assert cast(bytes, output).find(b"animal.txt") >= 0
```

```{toctree}
---
maxdepth: 4
---
api/modules
```