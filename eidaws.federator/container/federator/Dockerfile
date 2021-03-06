# Dockerizing eidaws-federator
#
# Build Container:
# docker build -t eidaws-federator:1.0 .
#
# Run Container:
# docker run [-d] [--rm] [--name eidaws-federator] -p 8080:8080 \
#   eidaws-federator:1.0
#
# Modify running container:
# docker exec -it eidaws-federator /bin/bash

# Base image
FROM docker.io/phusion/baseimage:bionic-1.0.0

ARG INSTANCES_DATASELECT_MINISEED=8
ARG INSTANCES_STATION_TEXT=4
ARG INSTANCES_STATION_XML=8
ARG INSTANCES_WFCATALOG_JSON=6
ARG DIR_CONTAINERFILE=eidaws.federator/container/federator

# Add label metadata
LABEL maintainer="Daniel Armbruster"
LABEL email="daniel.armbruster@sed.ethz.ch"

CMD ["/sbin/my_init"]

# System dependencies
RUN export DEBIAN_FRONTEND=noninteractive && \
  apt-get update && apt-get install -y libxml2-dev \
                                       libxslt-dev \
                                       python3.7 \
                                       python3.7-dev \
                                       python3.7-venv \
                                       python3-pip \
                                       nginx

# Configure nginx
ADD $DIR_CONTAINERFILE/conf.d /etc/nginx/conf.d
COPY $DIR_CONTAINERFILE/nginx.conf /etc/nginx
COPY $DIR_CONTAINERFILE/index.html /var/www/html

# Add the nginx service
RUN mkdir /etc/service/nginx && \
	echo "#!/bin/sh\nexec nginx 2>&1" > /etc/service/nginx/run && \
	chmod +x /etc/service/nginx/run

# Install backend services
RUN mkdir -p /var/www/eidaws-federator /run/eidaws-federator \
  /etc/eidaws /usr/local/src /var/log/eidaws-federator && \
  chown www-data:www-data /run/eidaws-federator
COPY . /usr/local/src/eidaws

# Setup virtualenv and install services
RUN python3.7 -m venv /var/www/eidaws-federator/venv && \
  /bin/bash -c "source /var/www/eidaws-federator/venv/bin/activate && \
  pip install --upgrade pip && \
  pip install -e /usr/local/src/eidaws/eidaws.utils && \
  pip install -e /usr/local/src/eidaws/eidaws.federator && deactivate"

# Backend service configuration files
COPY $DIR_CONTAINERFILE/*.yml \
  $DIR_CONTAINERFILE/logging.conf /etc/eidaws/
COPY $DIR_CONTAINERFILE/eidaws-federator.syslog-ng.conf \
  /etc/syslog-ng/conf.d/eidaws-federator.conf
COPY $DIR_CONTAINERFILE/eidaws-federator.logrotate.conf \
  /etc/logrotate.d/eidaws-federator
RUN chmod 644 /etc/logrotate.d/eidaws-federator

# Add backend services with installation script
COPY $DIR_CONTAINERFILE/*.template $DIR_CONTAINERFILE/install_backend.sh /tmp/
RUN chmod +x /tmp/install_backend.sh && \
  ./tmp/install_backend.sh \
  eida-federator-dataselect-miniseed $INSTANCES_DATASELECT_MINISEED && \
  ./tmp/install_backend.sh \
  eida-federator-station-text $INSTANCES_STATION_TEXT && \
  ./tmp/install_backend.sh \
  eida-federator-station-xml $INSTANCES_STATION_XML && \
  ./tmp/install_backend.sh \
  eida-federator-wfcatalog-json $INSTANCES_WFCATALOG_JSON

# Static content
COPY $DIR_CONTAINERFILE/static /var/www/eidaws-federator/static

# Expose HTTP default port
EXPOSE 8080

# Cleanup (baseimage recommended)
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
