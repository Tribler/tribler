Building on Mac
===============

We assume you've set up your environment to run Tribler.
Run the following commands in your terminal (assuming you are in the Tribler's repository root folder).

.. code-block:: none

    git describe | python -c "import sys; print(next(sys.stdin).lstrip('v'))" > .TriblerVersion
    git rev-parse HEAD > .TriblerCommit

    python ./build/update_version.py -r .

First, install additional requirements:

.. code-block:: none

    python -m pip install -r requirements-build.txt


Second, create the ``.dmg`` file in the ``dist`` directory.

.. code-block:: none

    export QT_QPA_PLATFORM=offscreen
    export QT_ACCESSIBILITY=1
    export QT_IM_MODULE=ibus
    export "TRIBLER_VERSION=$(head -n 1 .TriblerVersion)"

    ./build/mac/makedist_macos.sh

