Building on Linux
=================

We assume you've set up your environment to run Tribler.
Run the following commands in your terminal (assuming you are in the Tribler's repository root folder).

.. code-block:: none

    git describe | python -c "import sys; print(next(sys.stdin).lstrip('v'))" > .TriblerVersion
    git rev-parse HEAD > .TriblerCommit

First, install additional requirements:

.. code-block:: none

    sudo apt-get -y install debhelper devscripts
    sudo apt-get -y install libxcb-xinerama0-dev libqt5x11extras5 libgirepository1.0-dev
    python -m pip install --upgrade -r requirements-build.txt

Second, create the ``.deb`` file in the ``dist`` directory.

.. code-block:: none

    export QT_QPA_PLATFORM=offscreen
    export QT_ACCESSIBILITY=1
    export QT_IM_MODULE=ibus
    export "TRIBLER_VERSION=$(head -n 1 .TriblerVersion)"

    ./build/debian/makedist_debian.sh

