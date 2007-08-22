# !!! IMPORTANT
#
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
ARCH:=${shell arch}

ifeq ($(ARCH),ppc)
  # PPC
  OPENSSL_CONFIG=darwin-ppc-cc
  FFMPEG_CONFIG=--cpu=G4
else
  # INTEL
  OPENSSL_CONFIG=darwin-i386-cc
  FFMPEG_CONFIG=--cpu=pentium-m --enable-memalign-hack
endif

all:	clean dirs Tribler-${ARCH}.dmg ../lib

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

build/imagecontents/:	${SITEPACKAGES}/M2Crypto/ ${SITEPACKAGES}/Growl.py ${SITEPACKAGES}/vlc.so build/lib/ffmpeg build/lib/.vlc
	rm -rf $@
	mkdir -p $@

	cd .. && PYTHONPATH=mac/${SITEPACKAGES} ${PYTHON} -OO - < mac/setuptriblermac.py build
	mv ../build/* $@
	cd build && for i in `find lib -name "*.dylib"`; do mkdir -p ../${APPRES}/`dirname $$i`; cp $$i ../${APPRES}/$$i; done
	cp build/lib/ffmpeg ${APPRES}/lib/ffmpeg

	# Ditch Python documentation
	rm -rf build/imagecontents/Tribler.app/Contents/Frameworks/Python.framework/Versions/${PYTHON_VER}/Resources/English.lproj/Documentation

	# Thin everything for this architecture. Some things ship Universal (Python, wxPython, ...) and
	# others get a stub for the other architecture (things built by Universal Python)
	for i in `find build/imagecontents`; do ./smart_lipo_thin $$i; done

	# Background
	mkdir -p $@/.background
	cp background.png $@/.background

	# Volume Icon
	cp VolumeIcon.icns $@/.VolumeIcon.icns

	# Shortcut to /Applications
	ln -s /Applications $@/Applications

	touch $@

Tribler-${ARCH}.dmg:		build/imagecontents/ SLAResources.rsrc
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

build/temp/openssl-${OPENSSL_VER}.tar.gz:
	curl http://www.openssl.org/source/openssl-${OPENSSL_VER}.tar.gz -o $@

build/temp/.openssl:		build/temp/openssl-${OPENSSL_VER}.tar.gz
	cd build/temp && tar xfz openssl-${OPENSSL_VER}.tar.gz
	rm -rf build/temp/openssl
	mv build/temp/openssl-${OPENSSL_VER} build/temp/openssl

	cd build/temp/openssl && ./Configure ${OPENSSL_CONFIG}
	cd build/temp/openssl && make build_libs
	touch $@

build/temp/.m2crypto:
	svn co http://svn.tribler.org/m2crypto/branches/main build/temp/m2crypto
	touch $@

${SITEPACKAGES}/M2Crypto/:	build/temp/.openssl build/temp/.m2crypto
	cd build/temp/m2crypto && ${PYTHON} setup.py install --root ${PWD}/build/lib
	touch $@

# ----- VLC

VLCDIR=${PWD}/build/temp/vlc
VLCPREFIX=${VLCDIR}/install-root

build/temp/.vlc:
	svn co -r 21375 svn://svn.videolan.org/vlc/trunk ${VLCDIR}
	cd ${VLCDIR}/extras/contrib && ./bootstrap
	cd ${VLCDIR}/extras/contrib && make src
	touch $@

${VLCDIR}/Makefile:	build/temp/.vlc
	svn revert ${VLCDIR}/m4/* ${VLCDIR}/po/*
	cd ${VLCDIR} && ./bootstrap
	cd ${VLCDIR} && ./configure --enable-debug --disable-x11 --disable-xvideo --disable-glx --disable-qt4 --disable-sdl --enable-mad --enable-libdvbpsi --enable-a52 --disable-dvdplay --enable-dvdnav --enable-dvdread --enable-ffmpeg --enable-faad --enable-flac --enable-vorbis --enable-speex --enable-theora --enable-ogg --enable-shout --enable-cddb --disable-cddax --enable-vcdx --disable-skins --disable-skins2 --disable-wxwidgets --enable-freetype --enable-fribidi --disable-caca --enable-live555 --enable-dca --enable-goom --enable-modplug --enable-gnutls --enable-daap --disable-ncurses --enable-libtwolame --enable-x264 --enable-png --enable-realrtsp --disable-libtool --prefix=${VLCPREFIX}
	cd ${VLCDIR} && patch -p0 -N < ${PWD}/vlc-macosx-compile.patch
	cp mkinstalldirs ${VLCDIR}/autotools

${VLCPREFIX}/lib/libvlc.a:	${VLCDIR}/Makefile
	# build and install vlc
	cd ${VLCDIR} && ./compile

	# some necessary patches :( since these files differ between builds and architectures,
	# and one might want to run this Makefile several times in case of errors, we don't use patch
	cat ${VLCDIR}/Makefile | sed 's/vlc_app_DATA = VLC.app//;' > build/temp/Makefile.temp
	mv build/temp/Makefile.temp ${VLCDIR}/Makefile
	cat ${VLCDIR}/vlc-config | sed 's/^cflags_tuning=.*/cflags_tuning=""/; s/-lvlc-control//;' > build/temp/vlc-config.temp
	mv build/temp/vlc-config.temp ${VLCDIR}/vlc-config
	chmod a+x ${VLCDIR}/vlc-config

	cd ${VLCDIR} && make install

	# copy some missing libraries into the install-root
	for i in `${VLCDIR}/vlc-config --target builtin`; do cp ${VLCDIR}/$$i ${VLCPREFIX}/lib/vlc; done
	cp ${VLCDIR}/extras/contrib/vlc-lib/vlc_*.dylib ${VLCPREFIX}/lib/

${VLCPREFIX}/lib/python${PYTHON_VER}/site-packages/vlc.so:	${VLCPREFIX}/lib/libvlc.a
	# build python bindings
	cd ${VLCDIR}/bindings/python && ${PYTHON} setup.py install --prefix=${VLCPREFIX}

build/lib/.vlc:              ${VLCPREFIX}/lib/libvlc.a ${VLCPREFIX}/lib/python${PYTHON_VER}/site-packages/vlc.so
	# place the libraries/plugins in build/lib
	cd ${VLCPREFIX}/lib && for i in `find . -name "*.dylib"`; do mkdir -p ${PWD}/build/lib/`dirname $$i`; cp $$i ${PWD}/build/lib/$$i; done

	# fix dependencies of .dylib/.so libraries
	# replace @executable_path/lib/* => lib/*
	(for i in `find build/lib -name "*.dylib" -or -name "*.so"`; do otool -L $$i | perl -ne 'print "install_name_tool -change $$1 lib/$$2 '$$i'\n" if m#(\@executable_path/lib/(\S+))#;'; done) | bash -
	# replace $VLCPREFIX/lib/* => lib/*
	(for i in `find build/lib -name "*.dylib" -or -name "*.so"`; do otool -L $$i | perl -ne 'print "install_name_tool -change $$1 lib/$$2 '$$i'\n" if m#(${VLCPREFIX}/lib/(\S+))#;'; done) | bash -

	touch $@

${SITEPACKAGES}/vlc.so:		${VLCPREFIX}/lib/python${PYTHON_VER}/site-packages/vlc.so
	cp $< $@

../lib:			build/lib/.vlc
	# let run from source locate libraries
	rm -f ../lib
	ln -s ${PWD}/build/lib ../lib


# ----- FFmpeg

FFMPEG_CONFIG += --disable-vhook --disable-network --disable-ffserver --disable-ffplay

build/temp/.ffmpeg:
	svn co svn://svn.mplayerhq.hu/ffmpeg/trunk build/temp/ffmpeg
	touch $@

build/temp/ffmpeg/ffmpeg:	build/temp/.ffmpeg
	cd build/temp/ffmpeg && ./configure ${FFMPEG_CONFIG}
	cd build/temp/ffmpeg && make

build/lib/ffmpeg:		build/temp/ffmpeg/ffmpeg
	cp $^ $@

