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
default-libmysqlclient-dev \
# OpenCV & dependencies
python3-opencv \
libsm6 \
# python reqs
&& python3 -m pip install --no-cache-dir -r requirements.txt ortools redis \
# cleanup
&& apt-get remove -y build-essential \
&& apt-get remove -y python2.7 && rm -rf /usr/lib/python2.7 \
&& apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
&& rm -rf /var/lib/apt/lists/*

# tesseract
RUN apt-get update && apt-get -y install tesseract-ocr

# Copy everything to the working directory (Python files, templates, config) in one go.
COPY . /usr/src/app/

# Set Entrypoint with hard-coded options
ENTRYPOINT ["python3","start.py"]

# Default ports for PogoDroid, RGC and MAdmin
EXPOSE 8080 8000 5000
