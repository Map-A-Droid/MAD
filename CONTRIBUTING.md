Contributing to Map'A'Droid
***************************

The following summarizes the process for contributing changes.

Map'A'Droid utilizes `make` to build a consistent development environment across platforms. This helps ensure that any changes made pass required unit-tests and can identify regressions. To utilize `make` the following requirements need to be met:

 * Make
 * pip
 * pre-commit
 * docker
 * docker-compose
 * Python

Some of the dependencies will give additional information if its not installed.

Make Commands
**************

The following `make` commands are available:

 * `setup` - Install pre-commit and install the required git hooks. This should be run whenever new hooks are added (should be rare since most will be handled by pre-commit).
 * `clean` - Stop containers related to MAD development and cleanup ./tox folder
 * `build` - Multi-stage docker build. Build the MAD base image (local_mad_production) and build the development image (local_mad_development) without using the cache
 * `rebuild` - Same as `build` but can re-use cache
 * `up` - Start MariaDB and local_mad_development containers. MariaDB container does not have a persistent volume
 * `down` - Execute MariaDB and local_mad_development containers
 * `shell` - Execute `up` and gives user-level access to local_mad_development container
 * `root-shell` - Execute `up` and gives root-level access to local_mad_development container
 * `run` - Start MariaDB and local_mad_development containers. MariaDB container has a persistent volume
 * `tests` - Execute `up` and run all tests through tox
 * `unittests` - Execute `up` and run tox tests for py37
 * `shell-<pyxx>` - Execute `up` and grant user-level access with the tox virtual environment selected. Including `RECREATE=1` will rebuild the tox environment
 * `versions` - Lookup the current version for pip, pre-commit, docker, and docker-compose
