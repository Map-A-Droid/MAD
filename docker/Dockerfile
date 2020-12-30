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
