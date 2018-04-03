This section contains information about building Tribler on Windows. In the end you should be left with a ``.exe`` file which, when opened, enables users to install Tribler on their system.
This guide installs a 64-bit version of Tribler and has been tested on Windows 10 and Windows 2008 Server R2, 64-bit. It is recommended to create this builder on a system that is already able to run Tribler from a git checkout (it means that all the required packages required by Tribler are installed already). In case you want to build a 32 bit version, just install all the dependencies mentioned in 32 bit version.
Information about setting up a developer environment on Windows can be found on :ref:`tribler_dev_windows`.

**When you have installed zope, an empty** ``__init__.py`` **file must be present in the zope folder. If this file is missing, a** ``No module named zope`` **error will be thrown. Create this file in the** ``site-packages/zope`` **folder if it does not exist.**

Required packages
-----------------

To build a Tribler installer, you'll need some additional scripts and packages. The versions used as of writing this guide are mentioned next to the package or script.
* The git command tools (version 2.7.0) are required to fetch the latest release information. These can be downloaded from `here <https://git-scm.com/download/win>`_.
* PyInstaller, a tool to create an executable from python files. Install the latest version from pip: ``pip install pyinstaller``.
* The builder needs to find all packages that are required by Tribler so make sure you can run Tribler on your machine and that there are no missing dependencies.
* Nullsoft Scriptable Install System (NSIS) (version 2.5.0) is a script-driven Installer authoring tool for Microsoft Windows with minimal overhead. It can be downloaded `here <http://nsis.sourceforge.net/Download>`_. We selected version 2.5 as the uninstall functions were not called properly in 3.03b.
* Three plugins are required.The UAC plugin is the first. This can be downloaded from `here <http://nsis.sourceforge.net/UAC_plug-in>`_ (version 0.2.4c). How to install a plugin can be found `here <http://nsis.sourceforge.net/How_can_I_install_a_plugin>`_.
* The second plugin that is needed is AccessControl plug-in (version 1.0.8.1). It can be downloaded `here <http://nsis.sourceforge.net/AccessControl_plug-in>`_.
* The third plugin required is NSIS Simple Firewall Plugin (version 1.2.0). You can download it `here <http://nsis.sourceforge.net/NSIS_Simple_Firewall_Plugin>`_.
* The fourth plugin needed is NSProcess (Version 1.6.7), which can be downloaded `here <http://nsis.sourceforge.net/NsProcess_plugin>`_.
* A version of Microsoft Visual Studio should be installed (we use 2012), but make sure you do not have the build-tools only. The full (community) edition can be downloaded `here <https://www.visualstudio.com/en-us/downloads/download-visual-studio-vs.aspx>`_.

Building & Packaging Tribler
----------------------------

Start by cloning Tribler if you haven't done already (using the ``git clone --recursive`` command).
Next, create a ``build`` folder directly on your ``C:\`` drive.
Inside the ``build`` folder, put the following items:

1. A folder ``certs`` containing a ``.pfx`` key. In our case it's named ``swarmplayerprivatekey.pfx``. Make sure to rename paths in ``makedist_win.bat`` to match your file name.
2. A folder ``vlc`` that contains ``libvlc.dll``, ``libvlccore.dll`` and a directory ``plugins`` that contain the VLC plugins.
3. ``vc_redist_90.exe`` (Microsoft Visual C++ 2008 Redistributable Package), which is available `here <https://www.microsoft.com/en-us/download/details.aspx?id=15336>`_. In case you build 32 bit, get the x86 version `here <https://www.microsoft.com/en-us/download/details.aspx?id=29>`_. Don't forget to rename the file.
4. ``vc_redist_110.exe`` (Visual C++ Redistributable for Visual Studio 2012), which is available `here <https://www.microsoft.com/en-us/download/details.aspx?id=30679>`_. In case you build 32 bit, get the x86 version. Once more, don't forget to rename the file.
5. ``libsodium.dll`` which can be downloaded from `libsodium.org <https://download.libsodium.org/libsodium/releases/>`_ (as of writing version 1.0.8).
6. The openssl dll files ``libeay32.dll``, ``libssl32.dll`` and ``ssleay32.dll`` (place them in a directory named ``openssl``).

Then, set a ``PASSWORD`` `environment variable <https://www.microsoft.com/resources/documentation/windows/xp/all/proddocs/en-us/sysdm_advancd_environmnt_addchange_variable.mspx?mfr=true>`_ with its value set to the password matching the one set in your ``.pfx`` file.

Finally, open a command prompt and enter the following commands (Change 11.0 depending on your version of Microsoft Visual Studio):
Note that for building 32 bit you need to pass anything but 64, i.e. 32 or 86 to the ``update_version_from_git.py`` script.

.. code-block:: none

    cd tribler
    python Tribler/Main/Build/update_version_from_git.py 64
    win\makedist_win.bat 64

This builds an ``.exe`` installer which installs Tribler.
