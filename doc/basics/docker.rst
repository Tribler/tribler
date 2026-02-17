Running Tribler in Docker
=========================

In order to run Tribler from docker you only need a few steps.
We assume you have ``docker`` installed.

Currently, only running the (unstable!) ``latest`` release is supported.


Preparation
-----------

Fetch the docker image from ``docker.io``:

.. code-block::

    docker pull tribler/tribler:latest

Or, from ``ghcr.io``:

.. code-block::

    docker pull ghcr.io/tribler/tribler:latest

Running
-------

Choose a SECRET key for the background communication with Tribler.
In the following example, we use the key ``changeme`` (don't use this yourself).
To run the docker image:

.. code-block::

    docker run -e CORE_API_PORT=8085 -e CORE_API_KEY="changeme" \
               -e LANG=C.UTF-8 \
               -v ~/.Tribler:/home/ubuntu/.Tribler \
               -v ~/downloads/TriblerDownloads:/home/ubuntu/Downloads \
               -v $XDG_CACHE_HOME/tmp/:$XDG_CACHE_HOME/tmp/ -v /run:/run \
               --security-opt "apparmor:unconfined" \
               --net="host" \
               -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR -e DISPLAY=$DISPLAY \
               -e XDG_CACHE_HOME=$XDG_CACHE_HOME -e XAUTHORITY=$XAUTHORITY \
               -e DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
               --user $(id -u):$(id -g) -e BROWSER="x-www-browser" \
               -it ghcr.io/tribler/tribler:latest

*Alternatively*, if you want to run *without opening the web GUI* and *without a tray icon*:

.. code-block::

    docker run -e CORE_API_PORT=8085 -e CORE_API_KEY="changeme" \
               -e LANG=C.UTF-8 \
               -v ~/.Tribler:/home/ubuntu/.Tribler \
               -v ~/downloads/TriblerDownloads:/home/ubuntu/Downloads \
               --net="host" -it ghcr.io/tribler/tribler:latest -s

You can then open Tribler in your web browser at the URL:

.. code-block::

    localhost:8085/ui/#/downloads/all?key=changeme

Notes
-----

This script binds the local "state" directory (this is where Tribler puts its internal files) to ``~/.Tribler`` and your downloads directory (where your downloads end up) to ``~/downloads/TriblerDownloads``.
You can change these directories if you want to.

If you're planning on manipulating Tribler's internal REST API, you can access it through ``http://localhost:8085/docs``.
By default, the REST API is bound to localhost inside the container so to
access the APIs, network needs to be set to host (--net="host").

Stopping
--------

To stop Tribler, you should get the container id of your process and then stop it.
You can view all active docker containers using ``docker ps`` and you can stop a container id using ``docker stop``.
For most UNIX systems, the following command will stop your Tribler Docker container:

.. code-block::

    docker stop $(docker ps -aqf ancestor="ghcr.io/tribler/tribler:latest")
