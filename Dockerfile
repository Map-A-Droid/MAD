############################
# MAD
############################
FROM python:3.7-slim AS mad-core
# Working directory for the application
WORKDIR /usr/src/app

# copy requirements only, to reduce image size and improve cache usage
COPY requirements.txt /usr/src/app/

# Install required system packages + python requirements + cleanup in one layer (yields smaller docker image).
# If you try to debug the build you should split into single RUN commands
RUN export DEBIAN_FRONTEND=noninteractive && apt-get update \
&& apt-get install -y --no-install-recommends \
build-essential \
libglib2.0-0 \
default-libmysqlclient-dev \
libgl1 python-opencv \
libsm6 \
libxext6 \
libxrender-dev \
tk \
wget \
&& wget https://github.com/tesseract-ocr/tessdata/raw/master/eng.traineddata \
&& mkdir /usr/local/share/tessdata/ \
&& mv -v eng.traineddata /usr/local/share/tessdata/ \
# python reqs
&& python3 -m pip install --no-cache-dir -r requirements.txt ortools \
# cleanup
&& apt-get remove -y wget \
&& apt-get remove -y build-essential \
&& apt-get remove -y python2.7 && rm -rf /usr/lib/python2.7 \
&& apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
&& rm -rf /var/lib/apt/lists/*

RUN printf "deb http://ftp.de.debian.org/debian stretch main" >> /etc/apt/sources.list \
&& apt-get update && apt-get install libicu57

# tesseract from stretch-backport
RUN printf "deb http://httpredir.debian.org/debian stretch-backports main non-free\ndeb-src http://httpredir.debian.org/debian stretch-backports main non-free" >> /etc/apt/sources.list.d/backports.list \
&& apt-get update && apt-get -y --allow-unauthenticated -t stretch-backports install tesseract-ocr libtesseract-dev

# Copy everything to the working directory (Python files, templates, config) in one go.
COPY . /usr/src/app/

# Set Entrypoint with hard-coded options
ENTRYPOINT ["python3","start.py"]

# Default ports for PogoDroid, RGC and MAdmin
EXPOSE 8080 8000 5000

# Development env
FROM mad-core AS dev_test
RUN pip install tox
# Versions of python to install for pyenv. These are used when tox executes specific
# python versions. The correct versions need to be added to tox.ini under tox/envlist
ENV PYTHON_VERSIONS 3.6.0 3.7.0 3.8.0
COPY requirements-test.txt /usr/src/app/
ENTRYPOINT ["bash"]
# Need to re-add some required dependencies for tox to compile the new envs
RUN apt-get install -y --no-install-recommends \
# pyenv
build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
xz-utils tk-dev libffi-dev liblzma-dev python-openssl git \
# python build
libffi-dev libgdbm-dev libsqlite3-dev libssl-dev zlib1g-dev

# Map the user to avoid perm conflict
ARG USER_NAME=dockeruser
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID $USER_NAME; useradd -l -r -m -u $UID -g $GID $USER_NAME
ENV USER $USER_NAME
# Install pyenv
# @TODO - How to install as a user and not root?
ENV HOME=/home/dockeruser
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH="$PYENV_ROOT/bin:$PATH"
ENV PATH="$PYENV_ROOT/shims:$PATH"
RUN curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
RUN chown -R dockeruser:dockeruser -R $HOME
RUN for version in $PYTHON_VERSIONS; do \
      pyenv install $version; \
      pyenv local $version; \
      pip install --upgrade setuptools pip; \
      pyenv local --unset; \
    done
RUN echo "pyenv local $PYTHON_VERSIONS" >> ~/.bashrc
RUN chown -R dockeruser:dockeruser $HOME && pyenv local $PYTHON_VERSIONS
