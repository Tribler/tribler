Running Tribler in Docker
=========================

In order to run Tribler in Docker, create a file called ``Dockerfile`` and fill it with these contents:

.. code-block:: none

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


To build the docker image:

.. code-block:: bash

    docker build -t triblercore/triblercore:latest .


To run the built docker image:

.. code-block:: bash

    docker run -p 20100:20100 --net="host" triblercore/triblercore:latest

Note that by default, the REST API is bound to localhost inside the container so to
access the APIs, network needs to be set to host (--net="host").

To use the local state directory and downloads directory, the volumes can be mounted:

.. code-block:: bash

    docker run -p 20100:20100 --net="host" -v ~/.Tribler:/state -v ~/downloads/TriblerDownloads:/downloads triblercore/triblercore:latest


The REST APIs are now accessible at: http://localhost:20100/docs


Docker Compose
--------------

Tribler core can also be started using Docker Compose. For that, create a ``docker-compose.yml`` in the project root directory:

.. code-block:: none

    version: "3.3"

    services:
      tribler-core:
        image: triblercore/triblercore:latest
        container_name: triblercore
        build: .
        volumes:
          - "~/.Tribler:/state"
          - "~/Downloads/TriblerDownloads:/downloads"
        ports:
          - "20100:20100"
        environment:
          - CORE_API_PORT=20100
          - CORE_API_KEY=TEST
          - TORRENT_PORT=7000
          - TSTATEDIR=/state
          - HTTP_HOST=0.0.0.0

To run via docker compose:

.. code-block:: bash

    docker-compose up


To run in detached mode:

.. code-block:: bash

    docker-compose up -d


To stop Tribler:

.. code-block:: bash

    docker-compose down

