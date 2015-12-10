This page contains information about setting up a Tribler development environment on Windows. Unlike Linux based systems where installing third-party libraries is often a single `apt-get` command, installing and configuring the necessary libraries requires more attention on Windows. Moreover, the Windows environment has different file stuctures. For instance, where Linux is working extensively with .so (shared object) files, Windows uses DLL files.

## Introduction
In this guide, all required dependencies of Tribler will be explained. It presents how to install these dependencies. Some dependencies have to be built from source whereas other dependencies can be installed using a .msi installer. The guide targets Windows 10, 64-bit systems, however, it is probably not very hard to install 32-bit packages.

First, Python 2.7 should be installed. If you already have a Python version installed, please check whether this version is 64 bit before proceeding.

```
python -c "import struct;print( 8 * struct.calcsize('P'))"
```

This outputs whether your current installation is 32 or 64 bit.

Python can be downloaded from the official [Python website](https://www.python.org/downloads/release/python-2710/). You should download the Windows x86-64 MSI Installer which is an executable. **During the setup, remember to install pip/setuptools and to add Python to the PATH variable to access Python from the command line. The option to add Python to the PATH variable is unchecked by default!** You can verify whether Python is installed correctly by typing `python` in the command line. Also check whether pip is working by typing `pip` in the command line. If they are not working, check whether the PATH variables are correctly set.

If you did not change the default installation location, Python should be located at `C:\Python27\`. The third-party libraries are located in `C:\Python27\Lib\site-packages`. If you forgot to add Python to your PATH during the setup, you should need to add the  `C:\Python27\` and `C:\Python27\Scripts` directories to your PATH variable.

In order to compile some of the dependencies of Tribler, you will need the Visual C++ tools. Recently, Microsoft started to distribute these tools as stand-alone packages, removing the need to download the whole Visual Studio suite. The Visual C++ tools can be downloaded [here](http://blogs.msdn.com/b/vcblog/archive/2015/11/02/announcing-visual-c-build-tools-2015-standalone-c-tools-for-build-environments.aspx). These tools are still in pre-release.

The tools are also shipped with Visual Studio 2015 which can be downloaded from [here](https://www.visualstudio.com/downloads/download-visual-studio-vs). You should select the community edition. Visual Studio ships with a command line interface that can be used for building some of the Python packages. Moreover, it provides a nice IDE which can be used to work on Python projects. After installation of Visual Studio, you should install the Visual C++ tools. This can be done from within Visual Studio by creating a new Visual C++ project. Visual Studio then gives an option to install the Visual C++ developer tools.

## M2Crypto
The first package to be installed is M2Crypto which can be installed using pip (the M2Crypto binary is precompiled):

```
pip install --egg M2CryptoWin64
python -c "import M2Crypto" # test whether M2Crypto can be successfully imported
```

If the second statement does not raise an error, M2Crypto is successfully installed.

## wxPython
The graphical interface of Tribler is built using wxPython. wxPython can be installed by using the official win64 installer for Python 2.7 from [Sourceforge](http://sourceforge.net/projects/wxpython/files/wxPython). *At the time of writing, wx3 is not supported yet so you should install wx2.8* (make sure to install the unicode version). You can test whether wx can be successfully imported by running:

```
python -c "import wx"
```

This statement should proceed without error.

## pyWin32 Tools
In order to access some of the Windows API functions, pywin32 should be installed. The pywin32 installer can be downloaded from [Sourceforge](http://sourceforge.net/projects/pywin32/files/pywin32/) and make sure to select the amd64 version and the version compatible with Python 2.7.

## apsw
The apsw (Another Python SQLite Wrapper) installer can be downloaded from [GitHub](https://github.com/rogerbinns/apsw/releases). Again, make sure to select the amd64 version that is compatible with Python 2.7. You can test whether it is installed correctly by running:

```
python -c "import apsw"
```

## libtorrent
This package should be compiled from source. First, install Boost which can be downloaded from [SourceForge](http://sourceforge.net/projects/boost/files/boost-binaries/). Make sure to select the latest version and choose the version is compatible with your version of Visual C++ tools (probably msvc-14).

After installation, you should set an environment variable to let libtorrent know where Boost can be found. You can do this by going to Control Panel > System > Advanced > Environment Variables (more information about setting environment variables can be found [here](http://www.computerhope.com/issues/ch000549.htm)). Now add a variable named BOOST_ROOT and with the value of your Boost location. The default installation location for the Boost libraries is `C:\local\boost_<BOOST VERSION>` where `<BOOST VERSION>` indicates the installed Boost version.

Next, you should build Boost.build. You can do this by opening the Visual Studio command prompt and navigating to your Boost libraries. Navigate to `tools\build` and execute `bootstrap.bat`. This will create the `b2.exe` file. In order to invoke `b2` from anywhere in your command line, you should add the Boost directory to your user PATH environment variable. After modifying your PATH, you should reopen your command prompt.

Now, download the libtorrent source code from [GitHub](https://github.com/arvidn/libtorrent/releases) and extract it. Version 1.0.7 of Libtorrent seems to contain a bug when downloading torrents from the DHT so it is recommended to use the source code of version 1.0.6. Open the Developer Command Prompt shipped with Visual Studio (not the regular command prompt) and navigate to the location where you extracted the libtorrent source. In the directory where the libtorrent source code is located, navigate to `bindings\python` and build libtorrent by executing the following command (this takes a while so make sure to grab a coffee while waiting):

```
b2 boost=source libtorrent-link=static address-model=64
```

This command will build a static libtorrent 64-bit debug binary. You can also build a release binary by appending `release` to the command given above. After the build has been completed, the resulting `libtorrent.pyd` can be found in `LIBTORRENT_SOURCE\bindings\python\bin\msvc-14\debug\address-model-64\boost-source\link-static\` where `LIBTORRENT_SOURCE` indicates the directory with the libtorrent source files. Copy `libtorrent.pyd` to your site-packages location (the default location is `C:\Python27\Lib\site-packages`) and test libtorrent by executing:

```
python -c "import libtorrent"
```

## libsodium
Libsodium can be download as precompiled binary from [their website](https://download.libsodium.org/libsodium/releases/). Download the latest version, built with msvc. Extract the archive to any location on your machine. Next, you should add the location of the dynamic library to your `PATH` variables (either as system variable or as user variable). These library files can be found in `LIBSODIUM_ROOT\x64\Release\v140\dynamic\` where `LIBSODIUM_ROOT` is the location of your extracted libsodium files. After modifying your PATH, you should reopen your command prompt. You test whether Python is able to load `libsodium.dll` by executing:

```
python -c "import ctypes; ctypes.cdll.LoadLibrary('libsodium')"
```

## LevelDB
The next dependency to be installed is levelDB. LevelDB is a fast key-value storage written by Google. LevelDB itself is written in C++ but there are several Python wrappers available. In this guide, you will compile plyvel from source. Start by downloading the source code from [GitHub](https://github.com/numion/plyvel) (either clone the repository or download the source code as zip). This repo is a fork of the original plyvel wrapper with added support for Windows compilation. Open the Developer Command Prompt shipped with Visual Studio (not the regular command prompt) and navigate to the location where you extracted plyvel. To build, execute the following commands:

```
python bootstrap.py
bin\buildout.exe
bin\python.exe setup.py bdist_egg
python setup.py install
```

This should install the plyvel package. You can now test whether plyvel is working:

```
python -c "import plyvel"
```

## VLC
To install VLC, you can download the official installer from the [VideoLAN website](http://www.videolan.org/vlc/download-windows.html). Make sure to install the 64-bit version of VLC.

## Additional Packages
There are some additional packages which should be installed. They can easily be installed using pip:

```
pip install twisted requests pillow cherrypy cryptography decorator netifaces feedparser
```

## Running Tribler
You should now be able to run Tribler from command line. Grab a copy of the Tribler source code and navigate in a command line interface to the source code directory. Start Tribler by running:

```
python Tribler\Main\tribler.py
```

You might get errors about imports in the Tribler module. To fix this, you should add the location where the Tribler directory is located to the `PYTHONPATH` user environment variables. Information about changing environment variables can be found [here](http://www.computerhope.com/issues/ch000549.htm).

If there are any problems with the guide above, please feel free to fix any errors or [create an issue](https://github.com/Tribler/tribler/issues/new) so we can look into it.
