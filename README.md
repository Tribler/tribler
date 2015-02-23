# Tribler           [![Build Status](http://jenkins.tribler.org/job/Test_tribler_devel/badge/icon)](http://jenkins.tribler.org/job/Test_tribler_devel/)

_Towards making Bittorrent anonymous and impossible to shut down._

We use our own dedicated Tor-like network for anonymous torrent downloading. We implemented and enhanced the _Tor protocol specifications_ plus merged them with Bittorrent streaming. More info: https://github.com/Tribler/tribler/wiki
Tribler includes our own Tor-like onion routing network with hidden services based seeding and end-to-end encryption, detailed specs: https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications

The aim of Tribler is giving anonymous access to online (streaming) videos. We are trying to make privacy, strong cryptography and authentication the Internet norm.

Tribler currently offers a Youtube-style service. For instance, Bittorrent-compatible streaming, fast search, thumbnail previews and comments. For the past 9 years we have been building a very robust Peer-to-Peer system. Today Tribler is robust: "the only way to take Tribler down is to take The Internet down" (but a single software bug could end everything).

We make use of submodules, so remember using the --recursive argument when cloning this repo.

## Runtime dependencies

### Debian/Ubuntu/Mint
```bash
sudo apt-get install libav-tools libjs-excanvas libjs-mootools libsodium13 libx11-6 python-apsw python-cherrypy3 python-crypto python-cryptography python-feedparser python-gmpy python-leveldb python-libtorrent python-m2crypto python-netifaces python-pil python-pyasn1 python-requests python-twisted python-wxgtk2.8 python2.7 vlc
```
#### **Installing libsodium13 and python-cryptography on Ubuntu 14.04** 

While installing libsodium13 and python-cryptography on a clean Ubuntu 14.04 install (possibly other versions as well), the situation can occur where the Ubuntu terminal throws the following error when trying to install the dependencies mentioned earlier in the README.md: 

    E: Unable to locate package libsodium13
    E: Unable to locate package python-cryptography

This means that the required packages are not directly in the available package list of Ubuntu 14.04.

To install the packages, the required files have to be downloaded from their respecive websites.

For libsodium13, download libsodium13\_1.0.1-1\_<ProcessorType\>.deb from [http://packages.ubuntu.com/vivid/libsodium13](http://packages.ubuntu.com/vivid/libsodium13)

For python-cryptography, download python-cryptography\_0.5.2-1\_<ProcessorType\>.deb from [http://packages.ubuntu.com/utopic/python-cryptography](http://packages.ubuntu.com/utopic/python-cryptography)

###### **Installing the files**
**Through terminal**

After downloading files go to the download folder and install the files through terminal:

**For amd64:**

    cd ./Downloads
    dpkg -i libsodium13_1.0.1-1_amd64.deb
    dpkg -i python-cryptography_0.5.2-1_amd64.deb

**For i386:**
    
    cd ./Downloads
    dpkg -i libsodium13_1.0.1-1_i386.deb
    dpkg -i python-cryptography_0.5.2-1_i386.deb



**Through file navigator:**

Using the file navigator to go to the download folder and by clicking on the .deb files to have the software installer install the packages.

Now installing the list of dependencies should no longer throw an error.

### Windows and OSX
TODO

## Running Tribler from this repository
### Unix
First clone the repository:

```bash
git clone --recursive  git@github.com:Tribler/tribler.git
```

or, if you don't have added your ssh key to your github account:

```bash
git clone --recursive  https://github.com/Tribler/tribler.git
```

Done!
Now you can run tribler by executing the ```tribler.sh``` script on the root of the tree:

```bash
./tribler.sh
```
### Windows
TODO


# Packaging Tribler

## Debian and derivatives

```bash
sudo apt-get install devscripts
cd tribler
Tribler/Main/Build/update_version_from_git.py
debuild -i -us -uc -b
```

## OSX

```bash
cd tribler
mkdir vlc
# Copy the ffmpeg binary from its build directory
cp $HOME/Workspace/install/ffmpeg-2.2.4 vlc/ffmpeg
Tribler/Main/Build/update_version_from_git.py
./mac/makedistmac.sh
```
TODO: Add detailed build dependencies.

## Windows

```cmd
setlocal enabledelayedexpansion
call "c:\Program Files\Microsoft SDKs\Windows\v7.0\Bin\SetEnv.Cmd" /Release /x86
SET PATH=%PATH%;c:\windows\system32;c:\Program Files\Microsoft Visual Studio 9.0\VC\bin
cd tribler
python Tribler/Main/Build/update_version_from_git.py
xcopy c:\build\vlc vlc /E /I
win\makedist.bat
```

TODO: Add detailed build dependencies.

## Other Unixes

We don't have a generic setup.py yet.

So for the time being, the easiest way to package Tribler is to put ```Tribler/``` in ```/usr/share/tribler/``` and ```debian/bin/tribler``` in ```/usr/bin/```

A good reference for the dependency list is ```debian/control```

# Submodule notes
 - As updated submodules are in detached head state, remember to check out a branch before commiting changes on them.
 - If you forgot to check out a branch before doing a commit, you should get a warning telling you about it. To get the commit to a branch just check out the branch and do a git cherry-pick of the commit.
 - Take care of not accidentally commiting a submodule revision change with git commit -a
 - Do not commit a submodule update without running all the tests first and making sure the new code is not breaking Tribler.
