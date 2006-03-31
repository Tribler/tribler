			Tribler
	"The fastest way of social file sharing"
 	========================================

Please visit: http://www.tribler.org/. Tribler is based on the 
ABC BitTorrent client, please visit http://pingpong-abc.sourceforge.net/.


INSTALLING ON LINUX
-------------------

Tribler currently consists of the main source code and a modified version
of the M2Crypto library, called 0.15-ab1.

1. Make sure you have
        Python >= 2.4 
	OpenSSL >= 0.9.8
	swig >= 1.3.25
	wxPython >= 2.6 UNICODE

   Note that Tribler only works with wxPython UNICODE, not ANSI. As Python 
   2.3's unicode support is not perfect, Python 2.4 is prefered. OpenSSL 0.9.8 
   is required for Elliptic Curve crypto support.

2. Unpack the M2Crypto library, build and install:

        python2.4 setup.py build
	python2.4 setup.py install 
		
   When you've installed OpenSSL 0.9.8 in a non-standard directory, you must
   edit setup.py to point to this location. To install M2Crypto in another
   directory, use 
   
   	python2.4 setup.py install --prefix=/arno/pkgs/m2crypto-dev

   In that case you'll need to set the PYTHONPATH environment variable
   to point to that directory. PYTHONPATH can also be used to point
   to the ANSI version of wxPython when multiple versions are installed.
   E.g. 
	PYTHONPATH=/arno/pkgs/python-2.4.5/lib/python2.4/site-packages/wx-2.6-gtk2-ansi/

3. Unpack the main source code

4. Tribler can now be started by running

	python2.4 abc.py
	
   from the source directory. 
   

INSTALLING ON WINDOWS
---------------------

See the procedure for Linux and how_to_compile.txt in the source code. Note
that the former takes precedes over the latter. We'll update the latter in
the next release.

Arno Bakker, 2006-03-27
