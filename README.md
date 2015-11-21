# Tribler           [![Build Status](http://jenkins.tribler.org/job/Test_tribler_devel/badge/icon)](http://jenkins.tribler.org/job/Test_tribler_devel/)

_Towards making Bittorrent anonymous and impossible to shut down._

We use our own dedicated Tor-like network for anonymous torrent downloading. We implemented and enhanced the _Tor protocol specifications_ plus merged them with Bittorrent streaming. More info: https://github.com/Tribler/tribler/wiki
Tribler includes our own Tor-like onion routing network with hidden services based seeding and end-to-end encryption, detailed specs: https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications

The aim of Tribler is giving anonymous access to online (streaming) videos. We are trying to make privacy, strong cryptography and authentication the Internet norm.

Tribler currently offers a Youtube-style service. For instance, Bittorrent-compatible streaming, fast search, thumbnail previews and comments. For the past 9 years we have been building a very robust Peer-to-Peer system. Today Tribler is robust: "the only way to take Tribler down is to take The Internet down" (but a single software bug could end everything).

__We make use of submodules, so remember using the --recursive argument when cloning this repo.__

## Obtaining the latest release of Tribler

Just click [here](https://github.com/Tribler/tribler/releases/latest) and download the latest package for your OS.

## Obtaining support

If you found a bug or have a feature request, please make sure you read [contributing](CONTRIBUTING.md) and then [open an issue](https://github.com/Tribler/tribler/issues/new). We will have a look at it ASAP.

## Contributing

Contributions are very welcome!
If you are interested in contributing code or otherwise, please have a look at [contributing](CONTRIBUTING.md).
Have a look at the [issue tracker](https://github.com/Tribler/tribler/issues) if you are looking for inspiraton :).

## Getting your development environment up and running

We support development on Linux, OS X and Windows. We have written documentation that guides you through installing the required packages when setting up a Tribler development environment. Click [here](doc/Tribler development on Linux.md) for the guide on setting up a development environment on Linux distributions. Click [here](doc/Tribler development on Windows.md) for the guide on setting everything up on Windows. The guide for setting up the development environment on OS X can be found [here](doc/Tribler development on OS X.md).

### Running Tribler from this repository
#### Unix
First clone the repository:

```bash
git clone --recursive  git@github.com:Tribler/tribler.git
```

or, if you haven't added your ssh key to your github account:

```bash
git clone --recursive  https://github.com/Tribler/tribler.git
```

Done!
Now you can run tribler by executing the ```tribler.sh``` script on the root of the repository:

```bash
cd tribler
./tribler.sh
```

## Packaging Tribler

### Debian and derivatives

```bash
sudo apt-get install devscripts
cd tribler
Tribler/Main/Build/update_version_from_git.py
debuild -i -us -uc -b
```

### OSX

```bash
cd tribler
mkdir vlc
# Copy the ffmpeg binary from its build directory
cp $HOME/Workspace/install/ffmpeg-2.2.4 vlc/ffmpeg
Tribler/Main/Build/update_version_from_git.py
./mac/makedistmac.sh
```
TODO: Add detailed build dependencies.

### Windows

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

### Other Unixes

We don't have a generic setup.py yet.

So for the time being, the easiest way to package Tribler is to put ```Tribler/``` in ```/usr/share/tribler/``` and ```debian/bin/tribler``` in ```/usr/bin/```

A good reference for the dependency list is ```debian/control```

## Submodule notes
 - As updated submodules are in detached head state, remember to check out a branch before commiting changes on them.
 - If you forgot to check out a branch before doing a commit, you should get a warning telling you about it. To get the commit to a branch just check out the branch and do a git cherry-pick of the commit.
 - Take care of not accidentally commiting a submodule revision change with git commit -a
 - Do not commit a submodule update without running all the tests first and making sure the new code is not breaking Tribler.
