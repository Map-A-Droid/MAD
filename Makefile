CMD ?= bash
CONTAINER_NAME ?= mapadroid-dev
export UID ?= $(shell id -u)
export GID ?= $(shell id -g)


define PRE_COMMIT_ERR
    Install pre-commit @ https://pre-commit.com/#install then run
    source ~/.profile
endef

ifeq ($(shell which pip),)
    export pipbin ?= $(shell which pip)
else ifeq ($(shell which pip3),)
    export pipbin ?= $(shell which pip3)
else
    $(error, "pip not detected")
endif
ifeq (, $(shell which pre-commit))
    $(error $(PRE_COMMIT_ERR))
endif
ifeq (, $(shell which docker))
    $(error "Docker installation is missing or not available. https://docs.docker.com/get-docker/")
endif
ifeq (, $(shell which docker-compose))
    $(error "docker-compose installation is missing or not available. https://docs.docker.com/compose/install/")
endif
ifeq (, $(shell which docker-compose))
    $(error "docker-compose installation is missing or not available. https://docs.docker.com/compose/install/")
endif
compose_ver ?= $(shell docker-compose --version | cut -d' ' -f3 | cut -d '.' -f2)
ifeq (, compose_ver < 27)
    $(error "docker-compose too old. Update @ https://docs.docker.com/compose/install/")
endif

clean: clean-tox down

clean-tox:
	rm -rf .tox

build:
	docker-compose -f docker-compose-dev.yaml build --no-cache

rebuild:
	docker-compose -f docker-compose-dev.yaml build

setup-precommit:
	$(pipbin) install --user pre-commit
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

test tests:
	$(MAKE) shell CMD='sh -c "tox"'


# Run bash within a defined tox environment
# Specify a valid tox environment as such:
#       make shell-py37
# To force a recreation of the environment, specify the RECREATE environment variable with any value
#   make shell-py37 RECREATE=1
shell-%:
ifdef RECREATE
	# Forces recreation of environment
	$(MAKE) shell CMD="tox -e $* --recreate -- bash"
else
	$(MAKE) shell CMD="tox -e $* -- bash"
endif
