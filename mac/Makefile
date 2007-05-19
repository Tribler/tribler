# Building on Mac OS/X requires:
# * Python 2.5
# * wxPython 2.8-unicode
# * swig, subversion (available through MacPorts)
# * XCode 2.4+
#
# Use lower versions at your own risk.

OPENSSL_VER=0.9.8e
PYTHON_VER=2.5
PWD:=${shell pwd}

all:	clean dirs Tribler.dmg

clean:
	rm -rf build/imagecontents/ Tribler.dmg

SITEPACKAGES=build/lib/Library/Frameworks/Python.framework/Versions/${PYTHON_VER}/lib/python${PYTHON_VER}/site-packages
PYTHON=python${PYTHON_VER}

distclean:
	rm -rf build/ Tribler.dmg
	make dirs

dirs:
	mkdir -p build/temp build/lib

.PHONY: 		all clean distclean dirs

# ----- Tribler

APPRES=build/imagecontents/Tribler.app/Contents/Resources

build/imagecontents/:	${SITEPACKAGES}/M2Crypto/ ${SITEPACKAGES}/Growl.py ${SITEPACKAGES}/vlc.so
	rm -rf $@
	mkdir -p $@

	cd .. && PYTHONPATH=mac/${SITEPACKAGES} ${PYTHON} -OO - < mac/setuptriblermac.py build
	mv ../build/* $@
	cd build && for i in `find lib -name "*.dylib"`; do mkdir -p ../${APPRES}/`dirname $$i`; cp $$i ../${APPRES}/$$i; done

	# Sample Friend Icons
	#mkdir -p $@"/Sample Friend Icons"
	#cp ../icons/mugshots/*.bmp $@"/Sample Friend Icons"

	# Background
	mkdir -p $@/.background
	cp background.png $@/.background

	# Volume Icon
	cp VolumeIcon.icns $@/.VolumeIcon.icns

	# Shortcut to /Applications
	ln -s /Applications $@/Applications

	touch $@

Tribler.dmg:		build/imagecontents/ SLAResources.rsrc
	rm -f $@

	# create image
	hdiutil create -srcfolder $< -format UDRW -scrub -volname Tribler $@

	# open it
	hdiutil attach -readwrite -noverify -noautoopen $@ -mountpoint build/temp/mnt

	# make sure root folder is opened when image is
	bless --folder build/temp/mnt --openfolder build/temp/mnt
	# hack: wait for completion
	sleep 1

	# position items
	osascript -e "tell application \"Finder\"" \
	-e "   set f to POSIX file (\""${PWD}"/build/temp/mnt\" as string) as alias" \
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
	-e "       set the bounds of the container window to {50, 100, 600, 400}" \
	-e "       update without registering applications" \
	-e "       delay 5 -- Sync" \
	-e "       close" \
	-e "   end tell" \
	-e "   -- Sync" \
	-e "   delay 5" \
	-e "end tell" || true

	# turn on custom volume icon
	/Developer/Tools/SetFile -a C build/temp/mnt

	# close
	hdiutil detach build/temp/mnt

	# make read-only
	mv $@ build/temp/rw.dmg
	hdiutil convert build/temp/rw.dmg -format UDZO -imagekey zlib-level=9 -o $@
	rm -f build/temp/rw.dmg

	# add EULA
	hdiutil unflatten $@
	/Developer/Tools/DeRez -useDF SLAResources.rsrc > build/temp/sla.r
	/Developer/Tools/Rez -a build/temp/sla.r -o $@
	hdiutil flatten $@

# ----- Growl bindings

${SITEPACKAGES}/Growl.py:
	svn co http://src.growl.info/growl/trunk/Bindings/python build/temp/growl-bindings
	cd build/temp/growl-bindings && ${PYTHON} setup.py install --root ${PWD}/build/lib

# ----- OpenSSL and M2Crypto

${SITEPACKAGES}/M2Crypto/:
	curl http://www.openssl.org/source/openssl-${OPENSSL_VER}.tar.gz -o build/temp/openssl-${OPENSSL_VER}.tar.gz

	mkdir -p build/temp/openssl-i386
	mkdir -p build/temp/openssl-ppc

	cd build/temp && tar xfz openssl-${OPENSSL_VER}.tar.gz
	mv build/temp/openssl-${OPENSSL_VER} build/temp/openssl

	cd build/temp/openssl && make clean
	cd build/temp/openssl && ./Configure 386 darwin-i386-cc
	cd build/temp/openssl && make build_libs "CC=cc -arch i386"
	mv build/temp/openssl/*.a build/temp/openssl-i386

	cd build/temp/openssl && make clean
	cd build/temp/openssl && ./Configure darwin-ppc-cc
	cd build/temp/openssl && make build_libs "CC=cc -arch ppc"
	mv build/temp/openssl/*.a build/temp/openssl-ppc

	lipo -create -output build/temp/openssl/libcrypto.a build/temp/openssl-*/libcrypto.a
	ranlib build/temp/openssl/libcrypto.a

	lipo -create -output build/temp/openssl/libssl.a build/temp/openssl-*/libssl.a
	ranlib build/temp/openssl/libssl.a

	svn co http://svn.tribler.org/m2crypto/branches/main build/temp/m2crypto
	cd build/temp/m2crypto && ${PYTHON} setup.py install --root ${PWD}/build/lib

	touch $@

# ----- VLC

VLCDIR=${PWD}/build/temp/vlc

${VLCDIR}/.prereqs:
	svn co svn://svn.videolan.org/vlc/trunk ${VLCDIR}
	cd ${VLCDIR} && patch -p0 -N < ${PWD}/vlc-macosx.patch
	cd ${VLCDIR}/extras/contrib && ./bootstrap
	cd ${VLCDIR}/extras/contrib && make src
	touch $@

${VLCDIR}/Makefile:	${VLCDIR}/.prereqs
	cd ${VLCDIR} && ./bootstrap
	svn revert ${VLCDIR}/m4/*
	cd ${VLCDIR} && ./configure --enable-debug --disable-x11 --disable-xvideo --disable-glx --enable-sdl --enable-mad --enable-libdvbpsi --enable-a52 --disable-dvdplay --enable-dvdnav --enable-dvdread --enable-ffmpeg --enable-faad --enable-flac --enable-vorbis --enable-speex --enable-theora --enable-ogg --enable-shout --enable-cddb --disable-cddax --enable-vcdx --disable-skins --disable-skins2 --disable-wxwidgets --enable-freetype --enable-fribidi --disable-caca --enable-live555 --enable-dca --enable-goom --enable-modplug --enable-gnutls --enable-daap --enable-ncurses --enable-libtwolame --enable-x264 --enable-png --enable-realrtsp --disable-libtool --prefix=${VLCDIR}/install-root

${VLCDIR}/install-root/lib/libvlc.a:	${VLCDIR}/Makefile
	# build and install vlc
	cd ${VLCDIR} && ./compile
	cp mkinstalldirs ${VLCDIR}/autotools
	cd ${VLCDIR} && make install

	# copy some missing libraries into the install-root
	for i in `${VLCDIR}/vlc-config --target builtin`; do cp ${VLCDIR}/$$i ${VLCDIR}/install-root/lib/vlc; done
	cp ${VLCDIR}/extras/contrib/vlc-lib/vlc_*.dylib ${VLCDIR}/install-root/lib/

${VLCDIR}/install-root/lib/python${PYTHON_VER}/site-packages/vlc.so:	${VLCDIR}/install-root/lib/libvlc.a
	# build python bindings
	cd ${VLCDIR}/bindings/python && ${PYTHON} setup.py install --prefix=${VLCDIR}/install-root

${SITEPACKAGES}/vlc.so:		${VLCDIR}/install-root/lib/python${PYTHON_VER}/site-packages/vlc.so
	cd ${VLCDIR}/install-root/lib && for i in `find . -name "*.dylib"`; do mkdir -p ${PWD}/build/lib/`dirname $$i`; cp $$i ${PWD}/build/lib/$$i; done
	cp $< $@

	# fix dependencies of .dylib/.so libraries
	(for i in `find build/lib -name "*.dylib" -or -name "*.so"`; do otool -L $$i | perl -ne 'print "install_name_tool -change $$1 lib/$$2 '$$i'\n" if m#(\@executable_path/lib/(\S+))#;'; done) | bash -

	# let run from source locate libraries
	rm ../lib
	ln -s ${PWD}/build/lib ../lib

