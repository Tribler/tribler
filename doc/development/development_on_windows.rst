This section contains information about setting up a Tribler development environment on Windows. Unlike Linux based systems where installing third-party libraries is often a single ``apt-get`` command, installing and configuring the necessary libraries requires more attention on Windows. Moreover, the Windows environment has different file stuctures. For instance, where Linux is working extensively with .so (shared object) files, Windows uses DLL files.

Introduction
------------

In this guide, all required dependencies of Tribler will be explained. It presents how to install these dependencies. Some dependencies have to be built from source whereas other dependencies can be installed using a .msi installer. The guide targets Windows 10, 64-bit systems, however, it is probably not very hard to install 32-bit packages.

First, Python 2.7 should be installed. If you already have a Python version installed, please check whether this version is 64 bit before proceeding.

.. code-block:: none

    python -c "import struct;print( 8 * struct.calcsize('P'))"

This outputs whether your current installation is 32 or 64 bit.

Python can be downloaded from the official `Python website <https://www.python.org/downloads/release/python-2710/>`_. You should download the Windows x86-64 MSI Installer which is an executable. **During the setup, remember to install pip/setuptools and to add Python to the PATH variable to access Python from the command line. The option to add Python to the PATH variable is unchecked by default!** You can verify whether Python is installed correctly by typing ``python`` in the command line. Also check whether pip is working by typing ``pip`` in the command line. If they are not working, check whether the PATH variables are correctly set.

If you did not change the default installation location, Python should be located at ``C:\\Python27\\``. The third-party libraries are located in ``C:\\Python27\\Lib\\site-packages``. If you forgot to add Python to your PATH during the setup, you should need to add the ``C:\\Python27\\`` and ``C:\\Python27\\Scripts`` directories to your PATH variable.

In order to compile some of the dependencies of Tribler, you will need Visual Studio 2015 which can be downloaded from `here <https://www.visualstudio.com/downloads/download-visual-studio-vs>`_. You should select the community edition. Visual Studio ships with a command line interface that can be used for building some of the Python packages. Moreover, it provides a nice IDE which can be used to work on Python projects. After installation of Visual Studio, you should install the Visual C++ tools. This can be done from within Visual Studio by creating a new Visual C++ project. Visual Studio then gives an option to install the Visual C++ developer tools.

In case importing one of the modules fail due to a DLL error, you can inspect if there are files missing by opening it with `Dependency Walker <www.dependencywalker.com>`_. It should show missing dependencies. In our case, we were missing ``MSVCR100.DLL`` which belongs to the Microsoft Visual C++ 2010 SP1 Redistributable Package (x64). This package can be downloaded `from the Microsoft website <https://www.microsoft.com/en-us/download/details.aspx?id=13523>`_.
One other DLL that was missing was ``MSVCR110.DLL``, which belongs to the `Visual C++ Redistributable for Visual Studio 2012 Update 4 <https://www.microsoft.com/en-us/download/details.aspx?id=30679>`_.
After installing these two pakets, there should be no more import errors.

M2Crypto
--------

The first package to be installed is M2Crypto which can be installed using pip (the M2Crypto binary is precompiled):

.. code-block:: none

    pip install --egg M2CryptoWin64 # use M2CryptoWin32 for the 32-bit version of M2Crypto
    python -c "import M2Crypto" # test whether M2Crypto can be successfully imported

If the second statement does not raise an error, M2Crypto is successfully installed.

wxPython
--------

The graphical interface of Tribler is built using wxPython. wxPython can be installed by using the official win64 installer for Python 2.7 from `Sourceforge <http://sourceforge.net/projects/wxpython/files/wxPython>`_. **At the time of writing, wx3 is not supported yet so you should install wx2.8** (make sure to install the unicode version). You can test whether wx can be successfully imported by running:

.. code-block:: none

    python -c "import wx"

This statement should proceed without error.

pyWin32 Tools
-------------

In order to access some of the Windows API functions, pywin32 should be installed. The pywin32 installer can be downloaded from `Sourceforge <http://sourceforge.net/projects/pywin32/files/pywin32/>`_ and make sure to select the amd64 version and the version compatible with Python 2.7.

## apsw
The apsw (Another Python SQLite Wrapper) installer can be downloaded from `GitHub <https://github.com/rogerbinns/apsw/releases>`_. Again, make sure to select the amd64 version that is compatible with Python 2.7. You can test whether it is installed correctly by running:

.. code-block:: none

    python -c "import apsw"

libtorrent
----------

This package should be compiled from source. First, install Boost which can be downloaded from `SourceForge <http://sourceforge.net/projects/boost/files/boost-binaries/>`_. Make sure to select the latest version and choose the version is compatible with your version of Visual C++ tools (probably msvc-14).

After installation, you should set an environment variable to let libtorrent know where Boost can be found. You can do this by going to Control Panel > System > Advanced > Environment Variables (more information about setting environment variables can be found `here <http://www.computerhope.com/issues/ch000549.htm>`_). Now add a variable named BOOST_ROOT and with the value of your Boost location. The default installation location for the Boost libraries is ``C:\\local\\boost_<BOOST VERSION>`` where ``<BOOST VERSION>`` indicates the installed Boost version.

Next, you should build Boost.build. You can do this by opening the Visual Studio command prompt and navigating to your Boost libraries. Navigate to ``tools\\build`` and execute ``bootstrap.bat``. This will create the ``b2.exe`` file. In order to invoke ``b2`` from anywhere in your command line, you should add the Boost directory to your user PATH environment variable. After modifying your PATH, you should reopen your command prompt.

Now, download the libtorrent source code from `GitHub <https://github.com/arvidn/libtorrent/releases>`_ and extract it. It is advised to compile version 1.0.8. Note that you if you have a 32-bit system, you can download the ``.msi`` installer so you do not have to compile libtorrent yourself. Open the Developer Command Prompt shipped with Visual Studio (not the regular command prompt) and navigate to the location where you extracted the libtorrent source. In the directory where the libtorrent source code is located, navigate to ``bindings\\python`` and build libtorrent by executing the following command (this takes a while so make sure to grab a coffee while waiting):

.. code-block:: none

    b2 boost=source libtorrent-link=static address-model=64

This command will build a static libtorrent 64-bit debug binary. You can also build a release binary by appending ``release`` to the command given above. After the build has been completed, the resulting ``libtorrent.pyd`` can be found in ``LIBTORRENT_SOURCE\\bindings\\python\\bin\\msvc-14\\debug\\address-model-64\\boost-source\\link-static\\`` where ``LIBTORRENT_SOURCE`` indicates the directory with the libtorrent source files. Copy ``libtorrent.pyd`` to your site-packages location (the default location is ``C:\\Python27\\Lib\\site-packages``) and test libtorrent by executing:

.. code-block:: none

    python -c "import libtorrent"

libsodium
---------

Libsodium can be download as precompiled binary from `their website <https://download.libsodium.org/libsodium/releases/>`_. Download the latest version, built with msvc. Extract the archive to any location on your machine. Next, you should add the location of the dynamic library to your ``PATH`` variables (either as system variable or as user variable). These library files can be found in ``LIBSODIUM_ROOT\\x64\\Release\\v140\\dynamic\\`` where ``LIBSODIUM_ROOT`` is the location of your extracted libsodium files. After modifying your PATH, you should reopen your command prompt. You test whether Python is able to load ``libsodium.dll`` by executing:

.. code-block:: none

    python -c "import ctypes; ctypes.cdll.LoadLibrary('libsodium')"

LevelDB
-------

The next dependency to be installed is levelDB. LevelDB is a fast key-value storage written by Google. LevelDB itself is written in C++ but there are several Python wrappers available. In this guide, you will compile leveldb from source. First, download the source code from `GitHub <https://github.com/happynear/py-leveldb-windows>`_ (either clone the repository or download the source code as zip). The readme on this repo contains some basic instructions on how to compile leveldb.

Next, open the ``levedb_ext.sln`` file in Visual Studio. This guide is based on the ``x64 release`` configuration. If you want to build a 32-bit leveldb project, change the configuration to ``win32 release``.

You should edit the file paths of the include directories and the linker directories. These can be edited by right clicking on the project and selecting ``properties``. You will need to update ``additional include directories`` (under C/C++ -> general) to point to your Python include directory (often located in ``C:\\Python27\\include``). This is needed for the compilation of the Python bindings. Also, make sure that the following ``preprocessor definitions`` (found under C/C++ -> preprocessor) are defined: ``WIN32`` and ``LEVELDB_PLATFORM_WINDOWS``.

Next, ``additional library directories`` should be adjusted, found under Linker -> General. You should add the directory where your Python libraries are residing, often in ``C:\\Python27\\libs``.

Compile by pressing the ``build leveldb_ext`` in the build menu. If any errors are showing up during compilation, please refer to the Visual Studio log file and check what's going wrong. Often, this should be a missing include/linker directory. If compilation is successful, a ``leveldb_ext.pyd`` file should have been created in the project directory. Copy this file to your site-packages location and rename it to ``leveldb.pyd`` so Python is able to find it. You can test whether your binary is working by using the following command which should execute without any errors:

.. code-block:: none

    python -c "import leveldb"

VLC
---

To install VLC, you can download the official installer from the `VideoLAN website <http://www.videolan.org/vlc/download-windows.html>`_. Make sure to install the 64-bit version of VLC.

Additional Packages
-------------------

There are some additional packages which should be installed. They can easily be installed using pip:

.. code-block:: none

    pip install cherrypy chardet configobj cryptography decorator feedparser netifaces pillow twisted

Running Tribler
---------------

You should now be able to run Tribler from command line. Grab a copy of the Tribler source code and navigate in a command line interface to the source code directory. Start Tribler by running:

.. code-block:: none

    python Tribler\Main\tribler.py

You might get errors about imports in the Tribler module. To fix this, you should add the location where the Tribler directory is located to the ``PYTHONPATH`` user environment variables. Information about changing environment variables can be found `here <http://www.computerhope.com/issues/ch000549.htm>`_.

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
