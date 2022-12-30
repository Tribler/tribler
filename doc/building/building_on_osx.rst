This guide explains how to build Tribler on MacOS (10.10 to 10.13). The final result is a ``.dmg`` file which, when opened, allows ``Tribler.app`` to be copied to the Applications directory and or launched. Make sure the required packages required by Tribler are installed
from the  `Development instructions <../development/development_on_osx.rst>`_.

Building Tribler on macOS
-------------------------
Start by checking out the directory you want to clone (using ``git clone``). Open a terminal and ``cd`` to this new cloned directory (referenced to as ``tribler_source`` in this guide).

Next, we should inject version information into the files about the latest release:

.. code-block:: none

    git describe | python -c "import sys; print(next(sys.stdin).lstrip('v'))" > .TriblerVersion
    git rev-parse HEAD > .TriblerCommit

    python3 ./build/update_version.py -r .

Now execute the builder with the following command:

.. code-block:: none

    python3 -m pip install -r requirements-build.txt

    export QT_QPA_PLATFORM=offscreen
    export QT_ACCESSIBILITY=1
    export QT_IM_MODULE=ibus
    export "TRIBLER_VERSION=$(head -n 1 .TriblerVersion)"

    build/mac/makedist_macos.sh

This will create the ``.dmg`` file in the ``tribler_source/dist`` directory.
