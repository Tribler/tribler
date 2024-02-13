# libtorrent-1.2.19 does not support python 3.11 yet
FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libsodium23=1.0.18-1 \
    && rm -rf /var/lib/apt/lists/*

# Then, install pip dependencies so that it can be cached and does not
# need to be built every time the source code changes.
# This reduces the docker build time.
COPY ./requirements-core.txt /app/tribler/core-requirements.txt
RUN pip3 install -r /app/tribler/core-requirements.txt

RUN useradd -ms /bin/bash user

# Create default state and download directories and set the permissions
RUN chown -R user:user /app
RUN mkdir /state /downloads && chown -R user:user /state /downloads

# Copy the source code and set the working directory
COPY ./src /app/tribler/src/
WORKDIR /app/tribler/

# Set to -1 to use the default
ENV CORE_API_PORT=20100
ENV IPV8_PORT=7759
ENV TORRENT_PORT=-1
ENV DOWNLOAD_DIR=/downloads
ENV TSTATEDIR=/state
ENV HTTP_HOST=127.0.0.1
ENV HTTPS_HOST=127.0.0.1

VOLUME /state
VOLUME /downloads

USER user

CMD exec python3 /app/tribler/src/run_tribler_headless.py \
    --ipv8=${IPV8_PORT} \
    --libtorrent=${TORRENT_PORT} \
    --restapi_http_host=${HTTP_HOST} \
    --restapi_https_host=${HTTPS_HOST} \
    "--statedir=${TSTATEDIR}" \
    "--download_dir=${DOWNLOAD_DIR}"
