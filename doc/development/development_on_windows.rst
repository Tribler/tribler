This section contains information about setting up a Tribler development environment on Windows. Unlike Linux based systems where installing third-party libraries is often a single ``apt-get`` command, installing and configuring the necessary libraries requires more attention on Windows. Moreover, the Windows environment has different file structures. For instance, where Linux is working extensively with .so (shared object) files, Windows uses DLL files.

Introduction
------------

In this guide, all required dependencies of Tribler will be explained. It presents how to install these dependencies. Some dependencies have to be built from source whereas other dependencies can be installed using a .msi or .exe installer. The guide targets Windows 7 or higher, 64-bit systems, however, it is probably not very hard to install 32-bit packages.

First, Python 2.7 should be installed. If you already have a Python version installed, please check whether this version is 64 bit before proceeding.

.. code-block:: bash

    python -c "import struct;print( 8 * struct.calcsize('P'))"

This outputs whether your current installation is 32 or 64 bit.

Python can be downloaded from the official `Python website <https://www.python.org/downloads/release/python-2713/>`_. You should download the Windows x86-64 MSI Installer which is an executable. **During the setup, remember to install pip/setuptools and to add Python to the PATH variable to access Python from the command line. The option to add Python to the PATH variable is unchecked by default!** You can verify whether Python is installed correctly by typing ``python`` in the command line. Also check whether pip is working by typing ``pip`` in the command line. If they are not working, check whether the PATH variables are correctly set.

If you did not change the default installation location, Python should be located at ``C:\\Python27\\``. The third-party libraries are located in ``C:\\Python27\\Lib\\site-packages``. If you forgot to add Python to your PATH during the setup, you need to add the ``C:\\Python27\\`` and ``C:\\Python27\\Scripts`` directories to your PATH variable. Information about how to set path variable can be found `here <http://www.computerhope.com/issues/ch000549.htm>`__.

In order to compile some of the dependencies of Tribler, you will need Visual Studio 2015 which can be downloaded from `here <https://www.visualstudio.com/downloads/download-visual-studio-vs>`__ or `here <https://imagine.microsoft.com/en-us/Catalog/Product/101>`__. You should select the community edition. Visual Studio ships with a command line interface that can be used for building some of the Python packages. Moreover, it provides a nice IDE which can be used to work on Python projects. After installation of Visual Studio, you should install the Visual C++ tools. This can be done from within Visual Studio by creating a new Visual C++ project. Visual Studio then gives an option to install the Visual C++ developer tools.

In case importing one of the modules fail due to a DLL error, you can inspect if there are files missing by opening it with `Dependency Walker <www.dependencywalker.com>`_. It should show missing dependencies. In our case, we were missing ``MSVCR100.DLL`` which belongs to the Microsoft Visual C++ 2010 SP1 Redistributable Package (x64). This package can be downloaded `from the Microsoft website <https://www.microsoft.com/en-us/download/details.aspx?id=13523>`_.
One other DLL that was missing was ``MSVCR110.DLL``, which belongs to the `Visual C++ Redistributable for Visual Studio 2012 Update 4 <https://www.microsoft.com/en-us/download/details.aspx?id=30679>`_.
After installing these two packages, there should be no more import errors.
It may be required to enable Visual C++ Toolset on the Command Line if Native Command Line tool is not available. You can do that by following article `here <https://msdn.microsoft.com/en-us/library/x4d2c09s.aspx>`__.

PyQt5
-----

If you wish to run the Tribler Graphical User Interface, PyQt5 should be available on the system. While PyQt5 is available in the pip repository, this is only compatible with Python 3. There is an unofficial distribution available for Python 2.7 here `https://github.com/pyqt/python-qt5 <https://github.com/pyqt/python-qt5/>`_. You can simply install PyQt5 from this repository.

.. code-block:: bash

    pip install git+git://github.com/pyqt/python-qt5.git

After installation, check it was correctly installed

.. code-block:: bash

    python -c "import PyQt5" # this should work without any error

**Alternatively,** if above steps do not work, follow the instructions below.

Start by downloading the Qt library from `here <https://www.qt.io/download-open-source>`__. You can either compile it from source or use a Qt installer which automatically installs the pre-compiled libraries. Make sure to choose the correct distribution based on your platform(32/64 bit).

After the Qt installation is completed, PyQt5 should be compiled. This library depends on SIP, another library to automatically generate Python bindings from C++ code. Download the latest SIP version `here <https://riverbankcomputing.com/software/sip/download>`__, extract it, navigate to the directory where it has been extracted and compile/install it (don't forget to execute these commands in the Visual Studio command line):

.. code-block:: bash

    python configure.py
    nmake
    nmake install

Next, download PyQt5 from `here <https://sourceforge.net/projects/pyqt/files/PyQt5/>`__ and make sure that you download the version that matches with the version of Qt you installed in the previous steps. Extract the binary and compile it:

.. code-block:: bash

    python configure.py --qmake=<qmake_path> --disable=QtNfc --disable=QtBluetooth
    nmake
    nmake install
    python -c "import PyQt5" # this should work without any error

Note that ``<qmake_path>`` is the path to the qmake.exe file path. For eg. qmake could be here ``C:\Qt\Qt5.6.2\5.6\msvc2015_64\bin\qmake.exe`` but depends on your installation. Here, we are disabling QtNfc and QtBluetooth modules which contains classes that provide connectivity between NFC & Bluetooth enabled devices respectively which we do not require in Tribler. Moreover, not disabling these modules may lead to missing DLL files causing installation to fail. So, we can safely disable them. The installation can take a while. After it has finished, the PyQt5 library is installed correctly.

pyWin32 Tools
-------------

In order to access some of the Windows API functions, pywin32 should be installed. The pywin32 installer can be downloaded from `Sourceforge <http://sourceforge.net/projects/pywin32/files/pywin32/>`__ and make sure to select the amd64 version and the version compatible with Python 2.7.

libtorrent
----------

To install libtorrent, you can simply copy the ``libtorrent.pyd`` file from the Github repository `here <https://github.com/Tribler/libtorrent-binaries>`__ and place it inside your python site-packages directory.

**Alternatively,** if above does not work then you can try to compile from source. First, install Boost which can be downloaded from `SourceForge <http://sourceforge.net/projects/boost/files/boost-binaries/>`__. Make sure to select the latest version and choose the version is compatible with your version of Visual C++ tools (probably msvc-14).

After installation, you should set an environment variable to let libtorrent know where Boost can be found. You can do this by going to Control Panel > System > Advanced > Environment Variables (more information about setting environment variables can be found `here <http://www.computerhope.com/issues/ch000549.htm>`__). Now add a variable named BOOST_ROOT and with the value of your Boost location. The default installation location for the Boost libraries is ``C:\\local\\boost_<BOOST VERSION>`` where ``<BOOST VERSION>`` indicates the installed Boost version.

Next, you should build Boost.build. You can do this by opening the Visual Studio command prompt and navigating to your Boost libraries. Navigate to ``tools\\build`` and execute ``bootstrap.bat``. This will create the ``b2.exe`` file. In order to invoke ``b2`` from anywhere in your command line, you should add the Boost directory to your user PATH environment variable. After modifying your PATH, you should reopen your command prompt.

Now, download the libtorrent source code from `GitHub <https://github.com/arvidn/libtorrent/releases>`__ and extract it. It is advised to compile version 1.0.8. Note that you if you have a 32-bit system, you can download the ``.msi`` installer so you do not have to compile libtorrent yourself. Open the Developer Command Prompt shipped with Visual Studio (not the regular command prompt) and navigate to the location where you extracted the libtorrent source. In the directory where the libtorrent source code is located, navigate to ``bindings\\python`` and build libtorrent by executing the following command (this takes a while so make sure to grab a coffee while waiting):

.. code-block:: bash

    b2 boost=source libtorrent-link=static address-model=64

This command will build a static libtorrent 64-bit debug binary. You can also build a release binary by appending ``release`` to the command given above. After the build has been completed, the resulting ``libtorrent.pyd`` can be found in ``LIBTORRENT_SOURCE\\bindings\\python\\bin\\msvc-14\\debug\\address-model-64\\boost-source\\link-static\\`` where ``LIBTORRENT_SOURCE`` indicates the directory with the libtorrent source files. Copy ``libtorrent.pyd`` to your site-packages location (the default location is ``C:\\Python27\\Lib\\site-packages``)

After successfully copying the ``libtorrent.pyd`` file either compiled or from the repository, you can check if the installation was successful:

.. code-block:: bash

    python -c "import libtorrent" # this should work without any error

libsodium
---------

Libsodium can be download as precompiled binary from `their website <https://download.libsodium.org/libsodium/releases/>`__. Download the latest version, built with msvc. Extract the archive to any location on your machine. Next, you should add the location of the dynamic library to your ``PATH`` variables (either as system variable or as user variable). These library files can be found in ``LIBSODIUM_ROOT\\x64\\Release\\v140\\dynamic\\`` where ``LIBSODIUM_ROOT`` is the location of your extracted libsodium files. After modifying your PATH, you should reopen your command prompt. You test whether Python is able to load ``libsodium.dll`` by executing:

.. code-block:: bash

    python -c "import ctypes; ctypes.cdll.LoadLibrary('libsodium')"

VLC
---

To install VLC, you can download the official installer from the `VideoLAN website <http://www.videolan.org/vlc/download-windows.html>`_. Make sure to install the 64-bit version of VLC.

NumPy & SciPy
-------------
To install NumPy & SciPy, download the respective .whl files `here <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`__ and install using with pip as below. Make sure to download files with cp27 in names as they are for python 2.7

.. code-block:: bash

    pip install scipy‑0.19.1‑cp27‑cp27m‑win_amd64.whl
    pip install numpy‑1.13.1+mkl‑cp27‑cp27m‑win_amd64.whl



Additional Packages
-------------------

There are some additional packages which should be installed. They can easily be installed using pip:

.. code-block:: bash

    pip install cython  # Needs to be installed first for meliae
    pip install bitcoinlib cherrypy chardet configobj cryptography decorator libnacl meliae netifaces networkx pillow psutil typing twisted

Running Tribler
---------------

You should now be able to run Tribler from command line. Grab a copy of the Tribler source code and navigate in a command line interface to the source code directory. Start Tribler by running:

.. code-block:: bash

    python run_tribler.py

You might get errors about imports in the Tribler module. To fix this, you should add the location where the Tribler directory is located to the ``PYTHONPATH`` user environment variables. Information about changing environment variables can be found `here <http://www.computerhope.com/issues/ch000549.htm>`__.

If there are any problems with the guide above, please feel free to fix any errors or `create an issue <https://github.com/Tribler/tribler/issues/new>`_ so we can look into it.
