
This directory contains the build scripts for SwarmPlayer V2 for IE8.
That is, given IE8 doesn't support HTML5 we cannot use the SwarmTransport
concept for this browser. Instead, to have the SwarmPlayer concept work
on all platforms we use the SwarmPlugin with just Ogg/Theora+Vorbis formats
as a substitute. We call this SwarmPlayer V2 for IE8.

To prevent interference with the normal SwarmPlugin (that has all codecs),
the SwarmPlayer/Transport suite is independent from SwarmPlugin. That is,
SwarmPlayers have their own statedir (.SwarmPlayer), TCP ports, and ActiveX/
COM object IDs. In particular, 98FF91C0-A3B8-11DF-8555-0002A5D5C51B is the
objectID to use for the SwarmPlayer IE8.

Arno, 2010-08-09.

