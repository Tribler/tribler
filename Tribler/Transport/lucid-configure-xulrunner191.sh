#!/bin/sh -x
./configure --prefix=$HOME/pkgs/xulrunner-1.9.1.7 --enable-application=xulrunner \
	--enable-safe-browsing \
	--with-user-appdir=.mozilla \
	--without-system-jpeg \
	--with-system-zlib=/usr \
	--with-system-bz2=/usr \
	--disable-javaxpcom \
	--disable-crashreporter \
	--disable-elf-dynstr-gc \
	--disable-installer \
	--disable-strip \
	--disable-strip-libs \
	--disable-install-strip \
	--disable-updater \
	--enable-optimize \
	--enable-libnotify \
	--with-distribution-id=com.ubuntu 

