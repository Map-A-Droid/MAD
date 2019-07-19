# Basic docker image 
# Usage:
#   docker build -t pogomad .             # Build the docker Image
#   docker run -d pogomad start.py        # Launch Server

FROM python:3.7.1-slim

# Default ports for PogoDroid, RGC and MAdmin
EXPOSE 8080 8000 5000

# Working directory for the application
WORKDIR /usr/src/app

# Set Entrypoint with hard-coded options
ENTRYPOINT ["python"]
CMD ["./start.py"] 

# Install required system packages
RUN apt-get update && apt-get install -y --no-install-recommends libgeos-dev build-essential
RUN apt-get update && apt-get -y install libglib2.0-0 default-libmysqlclient-dev
RUN apt-get update && apt-get -y install tesseract-ocr libtesseract-dev
RUN apt-get -y install tk
RUN apt-get update

COPY requirements.txt /usr/src/app/
COPY requirements_ocr.txt /usr/src/app/

RUN apt-get update && apt-get install -y git && pip install -r requirements.txt
RUN apt-get update && apt-get install -y git && pip install -r requirements_ocr.txt

# Copy everything to the working directory (Python files, templates, config) in one go.
COPY . /usr/src/app/
