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

build/sla.r:		SLAResources.rsrc
	mkdir -p build
	/Developer/Tools/DeRez -useDF $< > $@

imagecontents/:		${SITEPACKAGES}/M2Crypto/ ${SITEPACKAGES}/Growl.py
	rm -rf $@
	mkdir -p $@

	cd .. && PYTHONPATH=mac/${SITEPACKAGES} ${PYTHON} -OO - < mac/setuptriblermac.py build
	mv ../build/* $@

	# Sample Friend Icons
	mkdir -p $@"/Sample Friend Icons"
	cp ../icons/mugshots/*.bmp $@"/Sample Friend Icons"

	# Background
	mkdir -p $@/.background
	cp background.png $@/.background

	# Volume Icon
	cp VolumeIcon.icns $@/.VolumeIcon.icns

	# Shortcut to /Applications
	ln -s /Applications $@/Applications

	touch $@

Tribler.dmg:		imagecontents/ build/sla.r
	rm -f $@
	mkdir -p build

	# create image
	hdiutil create -srcfolder $< -format UDRW -scrub -volname Tribler $@

	# open it
	hdiutil attach -readwrite -noverify -noautoopen $@ -mountpoint build/mnt

	# make sure root folder is opened when image is
	bless --folder build/mnt --openfolder build/mnt
	# hack: wait for completion
	sleep 1

	# position items
	osascript -e "tell application \"Finder\"" \
	-e "   set f to POSIX file (\""`pwd`"/build/mnt\" as string) as alias" \
	-e "   tell folder f" \
	-e "       open" \
	-e "       tell container window" \
	-e "          set toolbar visible to false" \
	-e "          set statusbar visible to false" \
	-e "          set current view to icon view" \
	-e "          delay 1 -- Sync" \
	-e "          set the bounds to {50, 100, 1000, 1000} -- Big size so the finder won't do silly things" \
	-e "       end tell" \
	-e "       delay 1 -- Sync" \
	-e "       set icon size of the icon view options of container window to 128" \
	-e "       set arrangement of the icon view options of container window to not arranged" \
	-e "       set background picture of the icon view options of container window to file \".background:background.png\"" \
	-e "       set position of item \"Tribler.app\" to {150, 140}" \
	-e "       set position of item \"Applications\" to {410, 140}" \
	-e "       set position of item \"Sample Friend Icons\" to {300, 400}" \
	-e "       set the bounds of the container window to {50, 100, 600, 400}" \
	-e "       update without registering applications" \
	-e "       delay 5 -- Sync" \
	-e "       close" \
	-e "   end tell" \
	-e "   -- Sync" \
	-e "   delay 5" \
	-e "end tell" || true

	# turn on custom volume icon
	/Developer/Tools/SetFile -a C build/mnt

	# close
	hdiutil detach build/mnt

	# make read-only
	mv $@ build/rw.dmg
	hdiutil convert build/rw.dmg -format UDZO -imagekey zlib-level=9 -o $@
	rm -f build/rw.dmg

	# add EULA
	hdiutil unflatten $@
	/Developer/Tools/Rez -a build/sla.r -o $@
	hdiutil flatten $@

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
