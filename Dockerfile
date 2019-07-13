###########################
# compile tesseract.
###########################
FROM python:3.7-slim AS tesseract_builder
RUN apt-get update && apt-get install -y automake ca-certificates g++ git libtool libleptonica-dev make pkg-config
RUN git clone https://github.com/tesseract-ocr/tesseract.git && cd tesseract && ./autogen.sh && ./configure && make &&  make install && ldconfig


############################
# MAD
############################
FROM python:3.7-slim
# Copy stuff from buildstage
COPY --from=tesseract_builder /usr/local/bin/tesseract /usr/local/bin/tesseract
COPY --from=tesseract_builder /usr/lib/x86_64-linux-gnu/libgomp.so.1 /usr/local/lib/libtesseract.a  /usr/local/lib/libtesseract.la /usr/local/lib/libtesseract.so.5 /usr/local/lib/libtesseract.so /usr/local/lib/libtesseract.so.5.0.0 /usr/lib/

# Working directory for the application
WORKDIR /usr/src/app

# copy requirements only, to reduce image size and improve cache usage
COPY requirements.txt /usr/src/app/

# Install required system packages + python requirements + cleanup in one layer (yields smaller docker image). 
# If you try to debug the build you should split into single RUN commands ;)
RUN export DEBIAN_FRONTEND=noninteractive && apt-get update \
&& apt-get install -y --no-install-recommends \
build-essential \
libglib2.0-0 \
default-libmysqlclient-dev \
python-opencv \
libsm6 \
libxext6 \
libxrender-dev \
libtesseract-dev \
tk \
wget \
&& wget https://github.com/tesseract-ocr/tessdata/raw/master/eng.traineddata \
&& mkdir /usr/local/share/tessdata/ \
&& mv -v eng.traineddata /usr/local/share/tessdata/ \
&& python3 -m pip install --no-cache-dir -r requirements.txt \
&& apt-get remove -y wget \
&& apt-get remove -y build-essential \
&& apt-get remove -y python2.7 && rm -rf /usr/lib/python2.7 \
&& apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
&& rm -rf /var/lib/apt/lists/*

# Copy everything to the working directory (Python files, templates, config) in one go.
COPY . /usr/src/app/

# Set Entrypoint with hard-coded options
ENTRYPOINT ["python3","start.py", "-wm", "-os"]

# Default ports for PogoDroid, RGC and MAdmin
EXPOSE 8080 8000 5000
