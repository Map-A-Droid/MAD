CMD ?= bash
CONTAINER_NAME ?= mapadroid-dev

define PIP_MISSING
Pip is missing or not available in PATH. If pip is not installed
instructions can be found at https://pip.pypa.io/en/stable/installing/
endef

define PRE_COMMIT_MISSING
Install pre-commit @ https://pre-commit.com/#install then run
source ~/.profile
endef

define DOCKER_MISSING
Docker installation is missing or not available. This could be caused by
not having docker installed or the user does not have access to docker.
Installation instructions can be found at
https://docs.docker.com/get-docker/
endef

define DOCKER_NOT_RUNNING
Docker is not running or the user does not have access to the Docker
Engine. Please verify that its running and you have access. On *nix
systems you can run the following commands to grant access:
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
endef

define DOCKER_COMPOSE_MISSING
docker-compose is not installed or not available in PATH. Installation
instructions can be found at https://docs.docker.com/compose/install/
If docker-compose is installed PATH needs to be corrected to include
the binary
endef

define DOCKER_COMPOSE_OLD
docker-compose is too old. Update docker-compose from the instructions at
https://docs.docker.com/compose/install/
endef

# Windows defines OS but *nix does not
ifdef OS
    SHELL := powershell.exe
    pip := $(shell Get-Command pip | Select-Object -ExpandProperty Source)
    precommit := $(shell Get-Command pre-commit | Select-Object -ExpandProperty Source)
    docker := $(shell Get-Command docker | Select-Object -ExpandProperty Source)
    docker_compose := $(shell Get-Command docker-compose | Select-Object -ExpandProperty Source)
    UID ?= 1000
    GID ?= 1000
else
    ifneq ($(shell $(WHICH) pip), "")
        pip := $(shell which pip)
    else ifeq ($(shell which pip3),)
        pip := $(shell which pip3)
    else
        pip := ""
    endif
    precommit := $(shell which pre-commit)
    docker := $(shell which docker)
    docker_compose := $(shell which docker-compose)
    UID ?= $(shell id -u)
    GID ?= $(shell id -g)
endif


ifeq (, $(pip))
    $(error $(PIP_MISSING))
endif
ifneq ($(VIRTUAL_ENV), )
    pip_precommit_installation := $(pip) install pre-commit
else
    pip_precommit_installation := $(pip) install --user pre-commit
endif
ifeq (, $(precommit))
    $(error $(PRE_COMMIT_MISSING))
endif
ifeq (, $(docker))
    $(error $(DOCKER_MISSING))
endif
ifeq (, $(shell docker info))
    $(error $(DOCKER_NOT_RUNNING))
endif
ifeq (, $(docker_compose))
    $(error $(DOCKER_COMPOSE_MISSING))
endif
compose_ver ?= $(shell docker-compose --version | cut -d' ' -f3 | cut -d '.' -f2)
ifeq (, compose_ver < 27)
    $(error $(DOCKER_COMPOSE_OLD))
endif

clean: clean-tox down

clean-tox:
	rm -rf .tox

build:
	docker-compose -f docker-compose-dev.yaml build --no-cache

rebuild:
	docker-compose -f docker-compose-dev.yaml build

setup-precommit:
	$(pip_precommit_installation)
	pre-commit install
	pre-commit install --hook-type commit-msg

setup: setup-precommit
	git config commit.template .gitmessage

up:
	docker-compose -f docker-compose-dev.yaml up --detach

shell: up
	docker-compose -f docker-compose-dev.yaml exec -u $(UID) $(CONTAINER_NAME) $(CMD)

root-shell: up
	docker-compose -f docker-compose-dev.yaml exec -u root $(CONTAINER_NAME) $(CMD)

down:
	docker-compose -f docker-compose-dev.yaml down

tests: up
	docker-compose -f docker-compose-dev.yaml exec -u $(UID) mapadroid-dev tox

unittests: up
	docker-compose -f docker-compose-dev.yaml exec -u $(UID) mapadroid-dev tox -e py37

# Run bash within a defined tox environment
# Specify a valid tox environment as such:
#       make shell-py37
# To force a recreation of the environment, specify the RECREATE environment variable with any value
#   make shell-py37 RECREATE=1
shell-%: up
ifdef RECREATE
	docker-compose -f docker-compose-dev.yaml exec -u $(UID) mapadroid-dev tox -e $* --recreate -- bash
else
	docker-compose -f docker-compose-dev.yaml exec -u $(UID) mapadroid-dev tox -e $* -- bash
endif

versions:
	$(pip) --version
	$(precommit) --version
	$(docker) --version
	$(docker_compose) --version
