This page contains information about setting up a Tribler development environment on Linux systems.

## Getting your development environment up and running

### Runtime dependencies

#### Debian/Ubuntu/Mint
```bash
sudo apt-get install libav-tools libjs-excanvas libjs-mootools libsodium13 libx11-6 python-apsw python-cherrypy3 python-crypto python-cryptography python-feedparser python-gmpy python-leveldb python-libtorrent python-m2crypto python-netifaces python-pil python-pyasn1 python-requests python-twisted python-wxgtk2.8 python2.7 vlc python-pip
pip install decorator
```
##### **Installing libsodium13 and python-cryptography on Ubuntu 14.04**

While installing libsodium13 and python-cryptography on a clean Ubuntu 14.04 install (possibly other versions as well), the situation can occur where the Ubuntu terminal throws the following error when trying to install the dependencies mentioned earlier in the README.md:

    E: Unable to locate package libsodium13
    E: Unable to locate package python-cryptography

This means that the required packages are not directly in the available package list of Ubuntu 14.04.

To install the packages, the required files have to be downloaded from their respecive websites.

For libsodium13, download libsodium13\_1.0.1-1\_<ProcessorType\>.deb from [http://packages.ubuntu.com/vivid/libsodium13](http://packages.ubuntu.com/vivid/libsodium13)

For python-cryptography, download python-cryptography\_0.8-1ubuntu2\_<ProcessorType\>.deb from [http://packages.ubuntu.com/vivid/python-cryptography](http://packages.ubuntu.com/vivid/python-cryptography)

###### **Installing the files**
**Through terminal**

After downloading files go to the download folder and install the files through terminal:

**For amd64:**

```bash
cd ./Downloads
dpkg -i libsodium13_1.0.1-1_amd64.deb
dpkg -i python-cryptography_0.8-1ubuntu2_amd64.deb
```
**For i386:**

```bash
cd ./Downloads
dpkg -i libsodium13_1.0.1-1_i386.deb
dpkg -i python-cryptography_0.8-1ubuntu2_i386.deb
```

**Through file navigator:**

Using the file navigator to go to the download folder and by clicking on the .deb files to have the software installer install the packages.

Now installing the list of dependencies should no longer throw an error.

If there are any problems with the guide above, please feel free to fix any errors or [create an issue](https://github.com/Tribler/tribler/issues/new) so we can look into it.
