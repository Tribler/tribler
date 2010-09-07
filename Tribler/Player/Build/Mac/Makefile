# Building on Mac OS/X requires:
# * Python 2.5
# * wxPython 2.8-unicode
# * py2app 0.3.6
# * swig, subversion (available through MacPorts)
# * XCode 2.4+
#
# Use lower versions at your own risk.

APPNAME=SwarmPlayer
PYTHON_VER=2.5
PWD:=${shell pwd}
ARCH:=${shell arch}

PYTHON=python${PYTHON_VER}

all:	clean SwarmPlayer-${ARCH}.dmg

clean:
	rm -rf build/imagecontents/ ${APPNAME}-${ARCH}.dmg

.PHONY: 		all clean dirs

# ----- SwarmPlayer 

APPRES=build/imagecontents/${APPNAME}.app/Contents/Resources

SRCDIR=../../../..

build/imagecontents/:
	rm -rf $@
	mkdir -p $@

	cd ${SRCDIR} && DYLD_LIBRARY_PATH=macbinaries PYTHONPATH=.:macbinaries ${PYTHON} -OO - < ${PWD}/setuptriblermac.py py2app
	mv ${SRCDIR}/dist/* $@

	# Thin everything for this architecture. Some things ship Universal (Python, wxPython, ...) and
	# others get a stub for the other architecture (things built by Universal Python)
	for i in `find build/imagecontents`; do ./smart_lipo_thin $$i; done

        # Replace any rogue references to local ones. For instance, some libraries are accidently
        # linked against /usr/local/lib/* or /opt/local/lib. Py2app puts them in the Frameworks dir,
        # but fails to correct the references in the binaries.
	#./process_libs build/imagecontents | bash -

	# Background
	mkdir -p $@/.background
	cp background.png $@/.background

	# Volume Icon
	cp VolumeIcon.icns $@/.VolumeIcon.icns

	# Shortcut to /Applications
	ln -s /Applications $@/Applications

	touch $@

${APPNAME}-${ARCH}.dmg:		build/imagecontents/ SLAResources.rsrc
	rm -f $@
	mkdir -p build/temp

	# create image
	hdiutil create -srcfolder $< -format UDRW -scrub -volname ${APPNAME} $@

	# open it
	hdiutil attach -readwrite -noverify -noautoopen $@ -mountpoint build/temp/mnt

	# make sure root folder is opened when image is
	bless --folder build/temp/mnt --openfolder build/temp/mnt
	# hack: wait for completion
	sleep 1

	# position items
	# oddly enough, 'set f .. as alias' can fail, but a reboot fixes that
	osascript -e "tell application \"Finder\"" \
	-e "   set f to POSIX file (\"${PWD}/build/temp/mnt\" as string) as alias" \
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
	-e "       set position of item \"${APPNAME}.app\" to {150, 140}" \
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
	/Developer/Tools/SetFile -a C build/temp/mnt || true

	# close
	hdiutil detach build/temp/mnt || true

	# make read-only
	mv $@ build/temp/rw.dmg
	hdiutil convert build/temp/rw.dmg -format UDZO -imagekey zlib-level=9 -o $@
	rm -f build/temp/rw.dmg

	# add EULA
	hdiutil unflatten $@
	/Developer/Tools/DeRez -useDF SLAResources.rsrc > build/temp/sla.r
	/Developer/Tools/Rez -a build/temp/sla.r -o $@
	hdiutil flatten $@
