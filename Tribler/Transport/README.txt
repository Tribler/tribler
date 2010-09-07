install dependancies:
 sudo apt-get install python-m2crypto python-openssl python2.6-wxgtk2.8 python-apsw

in one terminal:
 bzr branch lp:~j/+junk/tribe/
 cd tribe
 ant
 or for dev setup:
  echo `pwd` > ~/.mozilla/firefox/*default/extensions/tribe@p2pnext.org

restart firefox and open trib/test.html

to enable debugging open about:config and set
tribe.logging.enabled to true

Arno Remarks:
==========
- Using the domain name "p2p-next.org" gives problems on Linux
- To run from source, by linking ~/mozilla/firefox/..../tribe@p2pnext.org to Tribler/Transport
  you must add a symbolic link in the bgprocess dir that links to Tribler. Or use
  a different bgprocessd.
  
- The xulrunner that comes with Ubuntu lucid gives problems, I manually installed
  1.9.1.7 which does work:
  	
  wget http://releases.mozilla.org/pub/mozilla.org/xulrunner/releases/1.9.1.7/source/xulrunner-1.9.1.7.source.tar.bz2
  gtar -xvjf xulrunner-1.9.1.7.source.tar.bz2
  sudo apt-get build-dep xulrunner-1.9.2
  cd mozilla-1.9.1/
  .../Tribler/Transport/lucid-configure-xulrunner191.sh
  make 
  make install
  Make coffee :-(
  
- With xpitransmakedeb.sh you can create a .deb that installs SwarmTransport
  as a FX extension. Required software:
     devscripts
     mozilla-devscripts
     