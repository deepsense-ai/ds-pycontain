# Project overview

**ds_pycontain** is a python package which provides an abstraction over the docker API and provide Python REPL running in a docker container.

Supported functionality covers:
- Building docker images from Dockerfiles
- Pulling docker images from dockerhub (or similar)
- Running docker containers to execute a one-off command
- Running docker containers to execute a long-running process and communicate with it
- Run python commands in a container and get the result.

## Motivation

Main motivation is to allow to orchestrate running unsafe code or commands in isolated environment.
The docker API is quite complicated and not well documented or typed.
This project aims to provide a higher level abstraction over the docker API.

What is also provided is **a python REPL running in a docker container**.

This might be useful to improve security for execution of LLM models/agents generated code, which generally should not be trusted.

## Example code snippets

### Execute commands in container running in the background:

Below is a short snippet showcasing how to run docker container in the background and execute commands in it.

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

### Docker images

Images can be pulled from dockerhub or built from dockerfile.

```python
from ds_pycontain import DockerImage

# pull or use alpine:latest
image = DockerImage.from_tag("alpine")
# use provided tag to pull/use the image
image = DockerImage.from_tag("python", tag="3.9-slim")
#  use this dockerfile to build a new local image
image = DockerImage.from_dockerfile("example/Dockerfile")
# you can provide a directory path which contains Dockerfile, set custom image name
image = DockerImage.from_dockerfile("path/to/dir_with_Dockerfile/", name="cow")
```

### Python REPL running in docker container

Running Python code in docker container is rather easy with this package.

```python
  from ds_pycontain.python_dockerized_repl import PythonContainerREPL

  # To start python REPL in container it is easy,
  # just be aware that it will take some time to start the container
  # and ports might be allocated by OS, so use different port/retry
  # if you get error.
  repl = PythonContainerREPL(port=7121)

  # You can run python commands in the container
  # and it will keep state between commands.
  out1 = repl.exec("x = [1, 2, 3]")
  assert out1 == ""
  # Eval returns string representation of the python command
  # as it would be in python REPL:
  out2 = repl.eval("len(x)")
  assert out2 == "3"

  # Exec returns captured standard output (stdout)
  # so it won't return anything in this case:
  out3 = repl.exec("len(x)")
  assert out3 == ""
  # but exec with print works:
  out4 = repl.exec("print(len(x))")
  assert out4 == "3\n"

  # You can also get error messages if code is wrong:
  err = repl.exec("print(x")
  assert "SyntaxError" in err
```