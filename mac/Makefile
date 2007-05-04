# Building on Mac OS/X requires:
# * Python 2.5
# * wxPython 2.8-unicode
# * swig, subversion (available through MacPorts)
# * XCode 2.4+
#
# Use lower versions at your own risk.

OPENSSL_VER=0.9.8e
PYTHON_VER=2.5

all:	clean Tribler.dmg

clean:
	rm -rf imagecontents/ Tribler.dmg

SITEPACKAGES=Library/Frameworks/Python.framework/Versions/${PYTHON_VER}/lib/python${PYTHON_VER}/site-packages
PYTHON=python${PYTHON_VER}

distclean:		clean
	rm -rf m2crypto/ build/ openssl/ growl/ Library/ openssl-${OPENSSL_VER}.tar.gz

.PHONY: 		all clean distclean

# ----- Tribler

imagecontents/:		${SITEPACKAGES}/M2Crypto/ ${SITEPACKAGES}/Growl.py
	rm -rf $@
	mkdir -p $@

	cd .. && PYTHONPATH=mac/${SITEPACKAGES} ${PYTHON} -OO mac/setuptriblermac.py build
	mv ../build/* $@
	mkdir -p $@"/Sample Friend Icons"
	cp ../icons/mugshots/*.bmp $@"/Sample Friend Icons"

	touch $@

Tribler.dmg:		imagecontents/
	rm -f $@
	hdiutil create -srcfolder $< -format UDZO -fs HFS+ -volname Tribler $@

# ----- Growl bindings

growl-bindings/:
	svn co http://src.growl.info/growl/trunk/Bindings/python $@

${SITEPACKAGES}/Growl.py:	growl-bindings/
	cd $< && ${PYTHON} setup.py install --root ..
	touch $@

# ----- M2Crypto

m2crypto/:
	svn co http://svn.tribler.org/m2crypto/branches/main $@

${SITEPACKAGES}/M2Crypto/:	m2crypto/ openssl/libssl.a openssl/libcrypto.a
	cd m2crypto && ${PYTHON} setup.py install --root ..
	touch $@
	
# ----- OpenSSL

openssl-${OPENSSL_VER}.tar.gz:
	curl http://www.openssl.org/source/openssl-0.9.8e.tar.gz -o openssl-${OPENSSL_VER}.tar.gz

openssl/:			openssl-${OPENSSL_VER}.tar.gz
	tar xfz openssl-${OPENSSL_VER}.tar.gz
	mv openssl-${OPENSSL_VER} openssl

openssl/libcrypto.a openssl/libssl.a:	openssl/
	mkdir -p build/openssl-i386
	mkdir -p build/openssl-ppc

	cd openssl && make clean
	cd openssl && ./Configure 386 darwin-i386-cc
	cd openssl && make build_libs "CC=cc -arch i386"
	mv openssl/*.a build/openssl-i386

	cd openssl && make clean
	cd openssl && ./Configure darwin-ppc-cc
	cd openssl && make build_libs "CC=cc -arch ppc"
	mv openssl/*.a build/openssl-ppc

	lipo -create -output openssl/libcrypto.a build/openssl-*/libcrypto.a
	ranlib openssl/libcrypto.a

	lipo -create -output openssl/libssl.a build/openssl-*/libssl.a
	ranlib openssl/libssl.a
