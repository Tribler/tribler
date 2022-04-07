This section contains information about setting up a Tribler development environment on Windows. Unlike Linux based systems where installing third-party libraries is often a single ``apt-get`` command, installing and configuring the necessary libraries requires more attention on Windows. Moreover, the Windows environment has different file structures. For instance, where Linux is working extensively with .so (shared object) files, Windows uses DLL files.

Introduction
------------

In this guide, all required dependencies of Tribler will be explained. It presents how to install these dependencies. Some dependencies have to be built from source whereas other dependencies can be installed using a .msi or .exe installer. The guide targets Windows 7 or higher, 64-bit systems, however, it is probably not very hard to install 32-bit packages.

Prerequisites
------------

* `Python 3.8 <https://www.python.org/downloads/release/python-3813/>`_
* `OpenSSL <https://community.chocolatey.org/packages?q=openssl>`_
* `Libsodium <https://github.com/Tribler/py-ipv8/blob/master/doc/preliminaries/install_libsodium.rst>`_

Python Packages
-------------------

There are some additional packages which should be installed. They can easily be installed using pip:

.. code-block:: bash
    pip install --upgrade -r requirements.txt

Running Tribler
---------------

You should now be able to run Tribler from command line. Grab a copy of the Tribler source code and navigate in a command line interface to the source code directory. Start Tribler by executing the Batch script in the ``tribler/src`` directory:

.. code-block:: bash
    cd src
    tribler.bat

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
