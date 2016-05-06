This page contains information about building Tribler on Windows. In the end you should be left with a `.exe` file which, when opened, enables users to install Tribler on their system. 
This guide installs a 64-bit version of Tribler and has been tested on Windows 10 and Windows 2008 Server R2, 64-bit. It is recommended to create this builder on a system that is already able to run Tribler from a git checkout (it means that all the required packages required by Tribler are installed already). In case you want to build a 32 bit version, just install all the dependencies mentioned in 32 bit version.
Information about setting up a developer environment on Windows can be found [here](https://github.com/Tribler/tribler/blob/devel/doc/Tribler%20development%20on%20Windows.md).

**When you have installed zope, an empty ``__init__.py`` file must be present in the zope folder. If this file is missing, a ``No module named zope`` error will be thrown. Create this file in the ``site-packes/zope`` folder if it does not exist.**
 
# Required packages
To build a Tribler installer, you'll need some additional scripts and packages. The versions used as of writing this guide are mentioned next to the package or script.
* The git command tools (version 2.7.0) are required to fetch the latest release information. These can be downloaded from [here](https://git-scm.com/download/win). 
* Py2Exe (0.6.9), a tool to create an executeable from python files. Grab the latest version [here](http://sourceforge.net/projects/py2exe/files/py2exe/).
* The builder needs to find all packages that are required by Tribler so make sure you can run Tribler on your machine and that there are no missing dependencies.
* Nullsoft Scriptable Install System (NSIS) (version 2.5.0) is a script-driven Installer authoring tool for Microsoft Windows with minimal overhead. It can be downloaded [here](http://nsis.sourceforge.net/Download). We selected version 2.5 as the uninstall functions were not called properly in 3.03b.
* Three plugins are required.The UAC plugin is the first. This can be downloaded from [here](http://nsis.sourceforge.net/UAC_plug-in) (version 0.2.4c). How to install a plugin can be found [here](http://nsis.sourceforge.net/How_can_I_install_a_plugin).
* The second plugin that is needed is AccessControl plug-in (version 1.0.8.1). It can be downloaded [here](http://nsis.sourceforge.net/AccessControl_plug-in).
* The third plugin required is NSIS Simple Firewall Plugin (version 1.2.0). You can download it [here](http://nsis.sourceforge.net/NSIS_Simple_Firewall_Plugin).
* The fourth plugin needed is NSProcess (Version 1.6.7), which can be downloaded [here](http://nsis.sourceforge.net/NsProcess_plugin).
* A version of Microsoft Visual Studio should be installed (we use 2012), but make sure you do not have the build-tools only. The full (community) edition can be downloaded [here](https://www.visualstudio.com/en-us/downloads/download-visual-studio-vs.aspx).

# Building & Packaging Tribler
Start by cloning Tribler if you haven't done already (using the `git clone --recursive` command).
Next, create a `build` folder directly on your `C:\` drive.
Inside the `build` folder, put the following items:

1. A static version (64 bit, git-1d8f9b7) of ffmpeg, available [here](http://ffmpeg.zeranoe.com/builds/). Place it in a folder called `ffmpeg` in the `build` folder.
2. A folder `certs` containing a `.pfx` key. In our case it's named `swarmplayerprivatekey.pfx`. Make sure to rename paths in `makedist_win.bat` to match your file name.
3. A `vlc` folder containing a full instalation of vlc (Version 2.2.1).
4. `vc_redist_90.exe` (Microsoft Visual C++ 2008 Redistributable Package), which is available [here](https://www.microsoft.com/en-us/download/details.aspx?id=15336). In case you build 32 bit, get the x86 version [here](https://www.microsoft.com/en-us/download/details.aspx?id=29). Don't forget to rename the file.
5. `vc_redist_100.exe` (Microsoft Visual C++ 2010 Redistributable Package), which is available [here](https://www.microsoft.com/en-us/download/details.aspx?id=14632). In case you build 32 bit, get the x86 version [here](https://www.microsoft.com/en-us/download/details.aspx?id=5555). Again, don't forget to rename.
6. `vc_redist_110.exe` (Visual C++ Redistributable for Visual Studio 2012), which is available [here](https://www.microsoft.com/en-us/download/details.aspx?id=30679). In case you build 32 bit, get the x86 version. Once more, don't forget to rename the file.
7. `libsodium.dll` which can be downloaded from [libsodium.org](https://download.libsodium.org/libsodium/releases/) (as of writing version 1.0.8).

Then, set a `PASSWORD` [environment variable](https://www.microsoft.com/resources/documentation/windows/xp/all/proddocs/en-us/sysdm_advancd_environmnt_addchange_variable.mspx?mfr=true) with its value set to the password matching the one set in your `.pfx` file.

Finally, open a command prompt and enter the following commands (Change 11.0 depending on your version of Microsoft Visual Studio):
Note that for building 32 bit you need to pass anything but 64, i.e. 32 or 86 to the `update_version_from_git.py` script.
```
setlocal enabledelayedexpansion
call "C:\Program Files (x86)\Microsoft Visual Studio 11.0\VC\vcvarsall.bat"
SET PATH=%PATH%;C:\Windows\system32;C:\Program Files (x86)\Microsoft Visual Studio 11.0\VC\bin
dir
cd tribler
python Tribler/Main/Build/update_version_from_git.py 64
xcopy C:\build\vlc vlc /E /I
win\makedist_win.bat
```

This builds an `.exe` installer which installs Tribler when ran.
