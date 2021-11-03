This section contains information about setting up a Tribler development environment on Windows. Unlike Linux based systems where installing third-party libraries is often a single ``apt-get`` command, installing and configuring the necessary libraries requires more attention on Windows. Moreover, the Windows environment has different file structures. For instance, where Linux is working extensively with .so (shared object) files, Windows uses DLL files.

Introduction
------------

In this guide, all required dependencies of Tribler will be explained. It presents how to install these dependencies. Some dependencies have to be built from source whereas other dependencies can be installed using a .msi or .exe installer. The guide targets Windows 7 or higher, 64-bit systems, however, it is probably not very hard to install 32-bit packages.

First, Python 3 should be installed. If you already have a Python version installed, please check whether this version is 64 bit before proceeding.

.. code-block:: bash

    python -c "import struct;print( 8 * struct.calcsize('P'))"

This outputs whether your current installation is 32 or 64 bit.

Python can be downloaded from the official `Python website <https://www.python.org/downloads/>`_. You should download the Windows x86-64 MSI Installer which is an executable. **During the setup, remember to add Python to the PATH variable to access Python from the command line. The option to add Python to the PATH variable is unchecked by default!** You can verify whether Python is installed correctly by typing ``python`` in the command line. If they are not working, verify whether the PATH variables are correctly set. Instructions on how to set path variable can be found `here <http://www.computerhope.com/issues/ch000549.htm>`__.

In order to compile some of the dependencies of Tribler, you will need the Visual Studio installed which can be downloaded from `here <https://www.visualstudio.com/downloads/download-visual-studio-vs>`__ or `here <https://imagine.microsoft.com/en-us/Catalog/Product/101>`__. You should select the community edition. Visual Studio ships with a command line interface and all required tools that are used for building some of the Python packages. After the installation of Visual Studio, you should install the Visual C++ tools. This can be done from within Visual Studio by creating a new Visual C++ project. Visual Studio then gives an option to install the Visual C++ developer tools.

In case importing one of the modules fail due to a DLL error, you can inspect if there are files missing by opening it with `Dependency Walker <www.dependencywalker.com>`_. It should show missing dependencies.

libtorrent
----------

First, install Boost which can be downloaded from `SourceForge <http://sourceforge.net/projects/boost/files/boost-binaries/>`__. Make sure to select the latest version and choose the version is compatible with your version of Visual C++ tools (probably msvc-14).

After installation, you should set an environment variable to let libtorrent know where Boost can be found. You can do this by going to Control Panel > System > Advanced > Environment Variables (more information about setting environment variables can be found `here <http://www.computerhope.com/issues/ch000549.htm>`__). Now add a variable named BOOST_ROOT and with the value of your Boost location. The default installation location for the Boost libraries is ``C:\\local\\boost_<BOOST VERSION>`` where ``<BOOST VERSION>`` indicates the installed Boost version.

Next, you should build Boost.build. You can do this by opening the Visual Studio command prompt and navigating to your Boost libraries. Navigate to ``tools\\build`` and execute ``bootstrap.bat``. This will create the ``b2.exe`` file. In order to invoke ``b2`` from anywhere in your command line, you should add the Boost directory to your user PATH environment variable. After modifying your PATH, you should reopen your command prompt.

Now, download the libtorrent source code from `GitHub <https://github.com/arvidn/libtorrent/releases>`__ and extract it. It is advised to compile version 1.0.8. Note that you if you have a 32-bit system, you can download the ``.msi`` installer so you do not have to compile libtorrent yourself. Open the Developer Command Prompt shipped with Visual Studio (not the regular command prompt) and navigate to the location where you extracted the libtorrent source. In the directory where the libtorrent source code is located, navigate to ``bindings\\python`` and build libtorrent by executing the following command (this takes a while so make sure to grab a coffee while waiting):

.. code-block:: bash

    b2 boost=source libtorrent-link=static address-model=64

This command will build a static libtorrent 64-bit debug binary. You can also build a release binary by appending ``release`` to the command given above. After the build has been completed, the resulting ``libtorrent.pyd`` can be found in ``LIBTORRENT_SOURCE\\bindings\\python\\bin\\msvc-14\\debug\\address-model-64\\boost-source\\link-static\\`` where ``LIBTORRENT_SOURCE`` indicates the directory with the libtorrent source files. Copy ``libtorrent.pyd`` to your site-packages location (the default location is ``C:\\Python37\\Lib\\site-packages``)

After successfully copying the ``libtorrent.pyd`` file either compiled or from the repository, you can check if the installation was successful:

.. code-block:: bash

    python -c "import libtorrent" # this should work without any error

libsodium
---------

Libsodium is required for the ``libnacl`` library, used for cryptographic operations. Libsodium can be download as precompiled binary from `their website <https://download.libsodium.org/libsodium/releases/>`__. Download the latest version, built with msvc. Extract the archive to any location on your machine. Next, you should add the location of the dynamic library to your ``PATH`` variables (either as system variable or as user variable). These library files can be found in ``LIBSODIUM_ROOT\\x64\\Release\\v142\\dynamic\\`` where ``LIBSODIUM_ROOT`` is the location of your extracted libsodium files. After modifying your PATH, you should reopen your command prompt. You test whether Python is able to load ``libsodium.dll`` by executing:

.. code-block:: bash

    python -c "import ctypes; ctypes.cdll.LoadLibrary('libsodium')"

Note that this might fail on Python 3.8, since directories have to be explicitly whitelisted to load DLLs from them. You can either copy the ``libsodium.dll`` to your ``System32`` directory or by whitelisting that directory using ``os.add_dll_directory`` when running Tribler.


Additional Packages
-------------------

There are some additional packages which should be installed. They can easily be installed using pip:

.. code-block:: bash
    cd src
    pip install --upgrade -r requirements.txt

    cd src/pyipv8
    pip install --upgrade -r requirements.txt

Running Tribler
---------------

You should now be able to run Tribler from command line. Grab a copy of the Tribler source code and navigate in a command line interface to the source code directory. Start Tribler by executing the Batch script in the ``tribler/src`` directory:

.. code-block:: bash

    tribler.bat

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
