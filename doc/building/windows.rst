Building on Windows
===================

We assume you've set up your environment to run Tribler.
Don't forget to build the GUI using NPM!
Additionally, you will need to install:

- ``NSIS``, the ``SimpleFC`` plugin, and the ``nsProcess`` plugin.
- The latest ``libsodium.dll`` release.
- ``Microsoft Visual Studio 2022 Enterprise``. ``2022 Community`` will also work, but you need to edit `tribler.nsi` in the appropriate place.
- ``Windows Kits 10.0.19041.0``.
- ``OpenSSL``.

.. note::
 If you install any of these applications to non-default folders, you will need to modify the build scripts.

Run the following commands in your command prompt (assuming you are in the Tribler's repository root folder).

First, install additional requirements:

.. code-block::

    python -m pip install -r requirements-build.txt


Second, create the ``.exe`` file in the ``dist`` directory.
You can set the ``GITHUB_TAG`` to whatever you want to have your version set as.

.. code-block::

    set GITHUB_TAG="1.2.3"

    build\win\makedist_win.bat
