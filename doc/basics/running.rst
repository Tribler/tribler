Running Tribler from Source
===========================

In order to run Tribler from its source you will need to perform some setup.
We assume you have ``git`` and ``python`` installed.
If you want to run a GUI for Tribler, you will need ``npm`` installed too.


Steps
-----

1. Clone the Tribler repo:

.. code-block::

    git clone --recursive https://github.com/tribler/tribler

.. warning::
 Tribler uses submodules.
 If you (1) download the ZIP or (2) forget to recursively clone, your ``pyipv8`` folder will be empty.
 Repair the former by `downloading the IPv8 zip <https://github.com/Tribler/py-ipv8>`_ and extracting it in the ``pyipv8`` folder and repair the latter by running ``git submodule update --init``.
    
2. Install the python dependencies:

.. code-block::

    python -m pip install --upgrade -r tribler/requirements.txt

3. Build the GUI:

.. code-block::

    cd src/tribler/ui/
    npm install
    npm run build

4. Add the IPv8 submodule to your ``PYTHONPATH``. For example, (Windows) ``set PYTHONPATH=%PYTHONPATH%;pyipv8``, (Linux) ``export PYTHONPATH="${PYTHONPATH}:pyipv8"`` or (PyCharm) right click the ``pyipv8`` folder and ``Mark Directory as/Sources Root``.

5. Run Tribler:

.. code-block::

    cd src
    python run_tribler.py

Sometimes, you may run into platform-specific issues.
If this is your case, continue reading for your appropriate platform.


MacOS
-----

You may need to install  other packages separately:

.. code-block::

    brew install gmp mpfr libmpc libsodium

The security system on MacOS can prevent ``libsodium.dylib`` from being dynamically linked into Tribler when running Python.
If this library cannot be loaded, it gives an error that libsodium could not be found.
You can link or copy ``libsodium.dylib`` into the Tribler root directory:

.. code-block::

    cd tribler  # Wherever you have Tribler installed
    cp /usr/local/lib/libsodium.dylib ./ || cp /opt/local/lib/libsodium.dylib ./


Apple Silicon
-------------
There are currently no python bindings available to install from pip.
Therefore you need to build them from source.

To do this, please install openssl and boost first:

.. code-block:: bash

    brew install openssl boost boost-build boost-python3

And then follow the `instruction <https://github.com/arvidn/libtorrent/blob/v1.2.18/docs/python_binding.rst>`_.


Windows
-------

You may need to install the following packages separately:

* `OpenSSL <https://community.chocolatey.org/packages?q=openssl>`_
* `Libsodium <https://github.com/Tribler/py-ipv8/blob/master/doc/preliminaries/install_libsodium.rst>`_
