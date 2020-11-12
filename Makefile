CMD ?= bash
CONTAINER_NAME ?= mapadroid-dev
export UID ?= $(shell id -u)
export GID ?= $(shell id -g)


clean: clean-tox down

clean-tox:
	rm -rf .tox

build:
	docker-compose -f docker-compose-dev.yaml build --no-cache

rebuild:
	docker-compose -f docker-compose-dev.yaml build

setup-precommit:
	pip install --user pre-commit
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
# To force a recreation of the envrionment, specify the RECREATE environment variable with any value
#   make shell-py37 RECREATE=1
shell-%:
ifdef RECREATE
	# Forces recreation of environment
	$(MAKE) shell CMD="tox -e $* --recreate -- bash"
else
	$(MAKE) shell CMD="tox -e $* -- bash"
endif
