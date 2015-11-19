This page contains information about setting up a Tribler development environment on OS X. Unlike Linux based systems where installing third-party libraries is often a single `apt-get` command, installing and configuring the necessary libraries requires more attention on OS X. This guide has been tested with OS X 10.10.5 (Yosemite) but should also work for OS X 10.11 (El Capitan).

Note that the guide below assumes that Python is installed in the default location of Python (shipped with OS X). This location is normally in `/Library/Python/2.7`. Writing to this location requires root acccess when using easy_install or pip. To avoid root commands, you can install Python in a virtualenv. More information about setting up Python in a virtualenv can be found [here](http://www.marinamele.com/2014/05/install-python-virtualenv-virtualenvwrapper-mavericks.html).

## Introduction
Compilation of C/C++ libraries should be performed using Clang which is part of the Xcode Command Line Tools. The Python version shipped with OS X can be used and this guide has been tested using Python 2.7. The current installed version and binary of Python can be found by executing:

```
python --version # gets the python version
which python # prints the path of the Python executable
```

Note that the default location of third-party Python libraries (for example, installed with `pip`) can be found in `/Library/Python/2.7/site-packages`.

Many packages can be installed by using the popular brew and pip executables. Brew and pip can be installed by using:

```
ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
sudo easy_install pip
```

## Installing the Required Packages
In this section, the installation of the packages required by Tribler will be discussed in a step-by-step manner.

### Xcode Tools
The installation of Xcode is required in order to compile some C/C++ libraries. Xcode is an IDE developed by Apple and can be downloaded for free from the Mac App Store. After installation, the Command Line Tools should be installed by executing:

```
xcode-select --install
```

### WxPython
WxPython is the Graphical User Interface manager and an installer can be downloaded from [their website](http://www.wxpython.org/download.php). Note that at this point, Wx 2.8 should still be used but support for 2.8 will be dropped soon and the Wx 2.8 library should be replaced by Wx 3.0. You probably need the Cocoa version of Wx.

Note: there is a bug on OS X 10.11 (El Capitan) where the installer gives an error that there is no software available to install. A workaround for this is to install the required files manually. This can be done by opening the `.pkg` file and unzipping the `wxPython3.0-osx-cocoa-py2.7.pax` file. This will create a `usr` directory which should be copied to `/usr`. To link wx, you should run the `postflight.sh` as root.

### M2Crypto
To install M2Crypto, Openssl has to be installed first. The shipped version of openssl by Apple gives errors when compiling M2Crypto so a self-compiled version should be used. Start by downloading openssl 0.98 from [here](https://www.openssl.org/source/), extract it and install it:

```
./config --prefix=/usr/local
make && make test
sudo make install
openssl version # this should be 0.98
```

Also Swig is required for the compilation of the M2Crypto library. The easiest way to install it, it to download Swig from source [here](http://www.swig.org/download.html) and compile it using:

```
./configure
make
sudo make install
```

Now we can install M2Crypto. First download the [source](http://chandlerproject.org/Projects/MeTooCrypto) and install it:

```
python setup.py build build_ext --openssl=/usr/local
sudo python setup.py install build_ext --openssl=/usr/local
```

Test it out by executing:

```
python -c "import M2Crypto"
```

### Apsw
Apsw can be installed by brew but this does not seem to work to compile the last version (the Clang compiler uses the `sqlite.h` include shipped with Xcode which is outdated). Instead, the source should be downloaded from their [Github repository](https://github.com/rogerbinns/apsw) and compiled using:

```
sudo python setup.py fetch --all build --enable-all-extensions install test
```

### Libtorrent
An essential dependency of Tribler is libtorrent. libtorrent is dependent on Boost, a set of C++ libraries. To function correctly, Boost should be built from source (this will take a while):

```
brew install --build-from-source boost
brew install boost-python
```

Now we can install libtorrent:

```
brew install libtorrent-rasterbar --with-python
```

After the installation, brew gives some instructions to finish the installation, something like:

```
mkdir -p /Users/martijn/Library/Python/2.7/lib/python/site-packages
  echo 'import site; site.addsitedir("/usr/local/lib/python2.7/site-packages")' >> /Library/Python/2.7/site-packages/homebrew.pth
```

This command basically adds another location for the Python site-packages (the location where libtorrent-rasterbar is installed). This command should be executed since the location where brew installs the Python packages is not in sys.path. You can test whether libtorrent is correctly installed by executing:

```
python
>>> import libtorrent
```

### Other Packages
There are a bunch of other packages that can easily be installed using pip and brew:

```
brew install Pillow
pip install cherrypy pillow cffi cryptography decorator feedparser gmpy2 idna leveldb netifaces numpy pyasn1 pycparser requests twisted service_identity
```

If you encounter any error during the installation of Pillow, make sure that libjpeg and zlib are installed. They can be installed using:

```
brew tap homebrew/dupes
brew install libjpeg zlib
brew link --force zlib
```

Tribler should now be able to startup without warnings by executing this command in the Tribler root directory:

```
./tribler.sh
```

If there are any missing packages, they can often be installed by one pip or brew command. If there are any problems with the guide above, please feel free to fix any errors or [create an issue](https://github.com/Tribler/tribler/issues/new) so we can look into it.