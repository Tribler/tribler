			Tribler
	"The fastest way of social file sharing"
 	========================================

Please visit: http://www.tribler.org/. Tribler is based on the 
ABC BitTorrent client, please visit http://pingpong-abc.sourceforge.net/.

LICENSE
-------
See LICENSE.txt and binary-LICENSE.txt.


PREREQUISITES
-------------

Tribler consists of the main source code and a modified version of the
M2Crypto library. However, our modifications are now in the official
M2Crypto 0.16, so you should preferably use that version, available from
http://wiki.osafoundation.org/bin/view/Projects/MeTooCrypto    
Alternatively, look for our unofficial M2Crypto version 0.15-ab1 on the
Tribler website.

So make sure you have
        Python >= 2.4 
	OpenSSL >= 0.9.8
	swig >= 1.3.25
	wxPython >= 2.8 UNICODE (i.e., use --enable-unicode to build)
	M2Crypto >= 0.16
        pywin32 >= Build 208 (Windows only, for e.g. UPnP support)
	vlc >= 0.8.6a and its python bindings (for internal video player)

Note that Tribler only works with wxPython UNICODE, not ANSI. With small
adjustments it probably also works with wxPython 2.6.  Python 2.4 is prefered,
as Python 2.3's unicode support is not perfect, and 2.3's bsddb module does
not support the type of concurrency control we need. OpenSSL 0.9.8 is
required for Elliptic Curve crypto support.
   

INSTALLING ON LINUX
-------------------
 
1. Unpack the M2Crypto library, build and install:

        python2.4 setup.py build
	python2.4 setup.py install 
		
   When you've installed OpenSSL 0.9.8 in a non-standard directory, you must
   edit setup.py to point to this location. To install M2Crypto in another
   directory, use 
   
   	python2.4 setup.py install --prefix=/arno/pkgs/m2crypto-dev

   In that case you'll need to set the PYTHONPATH environment variable
   to point to that directory. PYTHONPATH can also be used to point
   to the UNICODE version of wxPython when multiple versions are installed.
   E.g. 
	PYTHONPATH=/arno/pkgs/python-2.4.3/lib/python2.4/site-packages/wx-2.6-gtk2-unicode/

2. Unpack the main source code

3. Tribler can now be started by running

	python2.4 abc.py
	
   from the source directory. 
   

INSTALLING ON WINDOWS
---------------------

To run Tribler from the source on Windows it is easiest to use binary distribution
of all packages. As of Python 2.4.4 the problem with interfacing with OpenSSL has 
disappeared. So the procedure is simply:

1. Download and install Python in e.g. C:\Python24

2. Download and install wxPython UNICODE for Python 2.4

3. Download and install OpenSSL >= 0.9.8 in e.g. C:\OpenSSL

4. Download and install M2Crypto for Python 2.4 

5. Download and uncompress Tribler source codes 

6. Run 
	C:\Python24\python2.4.exe abc.py
   from the source code directory.

***** Only if you need to use an older Python, read on ****

There is a problem with using OpenSSL 0.9.8 with Python <= 2.4.3 The problem and
its solution is described in the following links to the pycrypto mailing list, 
and involves recompiling Python yourself :-(

https://listserv.surfnet.nl/scripts/wa.exe?A2=ind0510&L=python-crypto&P=61
https://listserv.surfnet.nl/scripts/wa.exe?A2=ind0604&L=python-crypto&P=1049

Hence, the following procedure uses our pre-built Python binary required to
work with OpenSSL >= 0.9.8. Also M2Crypto may be hard to install, so we
provide a binary distribution for that as well. See below for information
on how to install that yourself.

1. Download and install Python in e.g. C:\Python24

2. Download and install wxPython UNICODE for Python 2.4

3. Download http://www.tribler.org/win/M2Crypto-py24.zip and uncompress it
   to C:\Python24\Lib\site-packages\M2Crypto\

4. Download and install OpenSSL in e.g. C:\OpenSSL

5. Download our pre-built python2.4.exe from 
	http://www.tribler.org/win/python2.4.exe
   and save it to C:\Python24\python2.4.exe

5. Download and uncompress Tribler source codes 

6. Run 
	C:\Python24\python2.4.exe abc.py
   from the source code directory.


Tips if you want to compile M2Crypto yourself using Microsoft Visual Studio
.NET 2003 (aka version 7.1).

1. Open a "Microsoft Visual Studio .NET 2003 Command Prompt" from the
   Microsoft Visual Studio .NET 2003 / Visual Studio .NET Tools  submenu of
   the Start Menu. Don't use a normal CMD prompt.

2. Make sure swig.exe is in your PATH:
  
  	set PATH=%PATH%;"C:\Program Files\swig"

   (In some cases python still doesn't find the swig.exe binary. In that case
   copy it to the current directory.)


  
3. Sometimes swig can't find its libraries, use the SWIG_LIB environment 
   variable:
  
  	set SWIG_LIB=C:\PROGRA~1\swig\lib
  
4. Edit M2Crypto's setup.py such that c:\\pkg is replaced with c:\\
   (it will now look for OpenSSL in C:\OpenSSL instead of C:\pkgs\OpenSSL)

5. Copy libeay32.lib and ssleay32.lib from C:\OpenSSL\lib\VC to the
   root of the M2Crypto source dir.
   
   	C:\M2Crypto> copy C:\OpenSSL\lib\VC\*.lib .
	
   Newer OpenSSL's have different versions of the libraries. In that case, 
   use the *MD.lib ones, and edit setup.py to link to the MD versions.


6. Now run

        C:\Python24\python2.4 setup.py build
	C:\Python24\python2.4 setup.py install 

   (In some cases, python won't find the __m2crypto.pyd installed. In that
   case copy it from \python25\lib\site-packages\M2Crypto\__m2crypto.pyd to 
   \python25\DLLs)


For information on how to build a binary distribution of Tribler, see
below. Be warned, however, because the
OpenSSL problem resurfaces there, and you need to recompile py2exe yourself,
as detailed in the above links to the pycrypto mailing list.

Arno Bakker, Jie Yang, 2007-04-19



HOW TO BUILD A BINARY DISTRIBUTION ON WINDOWS
---------------------------------------------

(from the original how_to_compile.txt)


1. Install Python 2.4 or greater   - http://www.python.org/

2. Install wxPython 2.6 or greater - http://www.wxpython.org/

3. Install NSIS 2.0 or greater     - http://nsis.sourceforge.net/

4. Install py2exe 0.6.2 or greater   - http://starship.python.net/crew/theller/py2exe/

5. Modify makedist.bat to point to the location for Python.
   i.e.:
   set PYTHON="C:\Python24\python.exe"

6. Modify makedist.bat to point to the location for NSIS.
   i.e.:
   set NSIS="C:\Program Files\NSIS\makensis.exe"

(Note: steps 7 and 8 are optional steps to build an executable that forces single processor affinity)
7. Install imagecfg                - http://www.robpol86.com/misc_pgs/imagecfg.php

8. Modify makedist.bat to point to the location for ImageCFG
   i.e.:
   set IMGCFG="C:\Program Files\Imagecfg\imagecfg.exe"

9. Run makedist.bat

10. An installer will be created in \dist under the current directory



BUILD TIPS
----------

* Should you want to build Python yourself and want it to use a non-default
  OpenSSL install, you'll have to edit Python-src/setup.py to include the
  right install dir in ssl_incs  and ssl_libs. As of M2Crypto-0.17 setup.py
  understands a --openssl=/ssldir parameter.
