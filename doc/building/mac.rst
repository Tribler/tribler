Building on Mac
===============

We assume you've set up your environment to run Tribler.
Don't forget to build the GUI using NPM!
Run the following commands in your terminal (assuming you are in the Tribler's repository root folder).

First, install additional requirements:

.. code-block::

    python -m pip install -r build/requirements.txt


Second, create the ``.dmg`` file in the ``dist`` directory.
You can set the ``GITHUB_TAG`` to whatever you want to have your version set as.

.. code-block::

    export GITHUB_TAG="1.2.3"

    ./build/mac/makedist_macos.sh
