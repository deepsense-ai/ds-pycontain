# [deepsense.ai](https://deepsense.ai) ds_pycontain
![CI](https://github.com/deepsense-ai/ds-pycontain/actions/workflows/ci.yml/badge.svg)
[![PyPI](https://img.shields.io/pypi/v/ds_pycontain?label=pypi%20package)](https://pypi.org/project/ds-pycontain/)
![PyPI - Downloads](https://img.shields.io/pypi/dm/ds-pycontain)

[Documentation](https://deepsense-ai.github.io/ds-pycontain/)

It is a simple wrapper library around docker python API to make it easier to use and to provide Python REPL running in a container.
In particular it was created for langchain isolated python REPL, so agents can run code in isolation.

**Warning**: This package requires docker to be installed and running on the host machine. It also needs more work to make it secure.

This package makes it a bit easier to:

* Build docker images from Dockerfiles or in-memory string.
* Pull docker images from dockerhub (or similar).
* Run docker container to execute a one-off command.
* Run docker container to execute a long-running process and communicate with it.
* Run python commands in a container and get the result.

Project boostraped with ds-template: [https://deepsense-ai.github.io/ds-template/](https://deepsense-ai.github.io/ds-template/).

# Example code snippet

## Execute commands in container running in the background:
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

## Docker images
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

## Python REPL running in docker container
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

# Setup developer environment

To start, you need to setup your local machine.

## Setup venv

You need to setup virtual environment, simplest way is to run from project root directory:

```bash
$ ./setup_dev_env.sh
$ source venv/bin/activate
```
This will create a new venv and run `pip install -r requirements-dev.txt`.

## Install pre-commit

To ensure code quality we use pre-commit hook with several checks. Setup it by:

```
pre-commit install
```

All updated files will be reformatted and linted before the commit.

To reformat and lint all files in the project, use:

`pre-commit run --all-files`

The used linters are configured in `.pre-commit-config.yaml`. You can use `pre-commit autoupdate` to bump tools to the latest versions.

# Project documentation

In `docs/` directory are Sphinx RST/Markdown files.

To build documentation locally, in your configured environment, you can use `build_docs.sh` script:

```bash
$ ./build_docs.sh
```

Then open `public/index.html` file.

Please read the official [Sphinx documentation](https://www.sphinx-doc.org/en/master/) for more details.



# Semantic version bump

To bump version of the library please use `bump2version` which will update all version strings.

NOTE: Configuration is in `.bumpversion.cfg` and **this is a main file defining version which should be updated only with bump2version**.

For convenience there is bash script which will create commit, to use it call:

```bash
# to create a new commit by increasing one semvar:
$ ./bump_version.sh minor
$ ./bump_version.sh major
$ ./bump_version.sh patch
# to see what is going to change run:
$ ./bump_version.sh --dry-run major
```
Script updates **VERSION** file and setup.cfg automatically uses that version.

You can configure it to update version string in other files as well - please check out the bump2version configuration file.

