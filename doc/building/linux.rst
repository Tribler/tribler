Building on Linux
=================

We assume you've set up your environment to run Tribler.
Don't forget to build the GUI using NPM!
Run the following commands in your terminal (assuming you are in the Tribler's repository root folder).

First, install additional requirements:

.. code-block::

    sudo apt-get -y install alien cpio=2.13+dfsg-7 devscripts fakeroot gir1.2-gtk-4.0 libgirepository1.0-dev rpm libcairo2-dev patchelf
    python -m pip install --upgrade -r build/requirements.txt

Second, create the ``.deb`` file in the ``dist`` directory.
You can set the ``GITHUB_TAG`` to whatever you want to have your version set as.

.. code-block::

    export GITHUB_TAG="1.2.3"

    ./build/debian/makedist_debian.sh
