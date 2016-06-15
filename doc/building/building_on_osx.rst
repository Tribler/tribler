This page contains information about building Tribler on OS X. The final result you should have is a `.dmg` file which, when opened, allows `Tribler.app` to be copied to the Applications directory. This guide has been tested on OS X 10.11 (El Capitan). It is recommended to run this builder on a system that is already able to run Tribler without problems (it means that all the required packages required by Tribler are installed already). Information about setting up a developer environment on OS X can be found [here](https://github.com/Tribler/tribler/blob/devel/doc/Tribler%20development%20on%20OS%20X.md).

## Required packages
To build and distribute Tribler, there are some required scripts and packages:
* The git command tools are required to fetch the latest release information. They are installed when you start Xcode for the first time but you can also install it using `brew` or another package library.
* Py2app. The built-in version of py2app does not function correctly when System Integrity Protection (SIP) is turned on. You can either turn SIP off (instructions on how to do this can be found [here](http://www.imore.com/el-capitan-system-integrity-protection-helps-keep-malware-away)) or you can install a more recent version of py2app using PIP in your user-defined `site-packages`. Note that you should place the `site-packages` directory with py2app in it higher in the `PYTHONPATH` environment variable than the `site-packages` directory managed by the system. Otherwise, the builder will chooose the py2app package installed by the system.
* The builder needs to find all packages that are required by Tribler so make sure you can run Tribler on your machine and that there are no missing dependencies.
* In order to attach the EULA to the `.dmg` file, we make use of the `eulagise` script. This script is written in PERL and is based on a more fully-featured script. The script can be dowloaded from [GitHub](https://github.com/CompoFX/compo/blob/master/tool/eulagise.pl). The builder expects the script to be executable and added to the `PATH` environment variable. This can be done with the following commands:

```
cp eulagise.pl /usr/local/bin/eulagise
chmod +x /usr/local/bin/eulagise
eulagise # to test it - it should show that you should add some flags
```

## Building Tribler on OS X
Start by checking out the directory you want to clone (using `git clone --recursive`). Open a terminal and `cd` to this new cloned directory (referenced to as `tribler_source` in this guide).

First we need to copy the ffmpeg library to `tribler_source`. You can download this file from [here](http://evermeet.cx/ffmpeg/). Next, create a directory named `vlc` in `tribler_source` and copy the `ffmpeg` file to that directory. Make sure to name the file `ffmpeg`, otherwise the builder cannot find it.

Next, we should inject version information into the files about the latest release. This is done by the `update_version_from_git.py` script found in `Tribler/Main/Build`. Invoke it from the `tribler_source` directory by executing:

```
Tribler/Main/Build/update_version_from_git.py
```

Before we can build the `.dmg` file, some environment variables need to be set:

```
export MACOSX_DEPLOYMENT_TARGET=10.11
export CFLAGS=' -mmacosx-version-min=10.6 -O -g '
export CXXFLAGS=' -mmacosx-version-min=10.6 -O -g '
```

If you are building on another environment, you should change `MACOSX_DEPLOYMENT_TARGET` to match your version of OS X. The `-mmacosx-version-min` is required so the builder can optimize the build depending on the minimum supported version.

Now execute the builder with the following command:

```
./mac/makedistmac_64bit.sh
```

This will create the `.dmg` file in the `tribler_source/dist` directory.
