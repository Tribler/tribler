This document describes the format for storing, saving and
loading metadata entries to/from file-based format that is
sent as torrents by the Channels system.

Metadata lifecycle in the Channels system
=========================================
It is easiest to show the inner workings of the Channels system
by following the full path of a metadata entry from its creation to the moment it arrives
into another host's database.
In brief, the channel is going through the following stages during its lifetime:

* `Channel creation`_ or `Torrent metadata entry creation`_ - as a tree of metadata entries in the PonyORM DB
* `Committing the channel contents to disk`_ in the form of a serialized, append-only stream of updates,
  broken down into mdblob files
* Creating a torrent from the serialized stream/mdblob files
* `Delivering the channel entry to another host`_ via e.g. gossip through RemoteQuery community
* Downloading the channel by infohash (using Libtorrent)
* `Processing the channel from disk`_ on the remote host and updating the remote hosts' DB accordingly

The discrete clock
------------------

An important part of the Channels design is its usage of discrete timestamps to note
the order of creation/modification of metadata entries. The timestamps' meaning is local
to the public key domain. This allows us to use a simple increasing discrete counter
that is initiated at Tribler startup from the local time.
The counter is increased by +1 on each ``tick`` (e.g. generation of a timestamp).


Channel creation
----------------

The user creates a personal channel by creating a ``ChannelTorrent`` entry in the database:

+-----------------+----------------------------------------+---------------------------------------------+
| Property        | Value                                  | Comment                                     |
+=================+========================================+=============================================+
| metadata_type   | 400  (CHANNEL_TORRENT)                 | used as the "discriminator" by PonyORM      |
+-----------------+----------------------------------------+---------------------------------------------+
| flags           | 0                                      |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| public_key      | host's public key                      | identifies the "user domain" of the entry   |
+-----------------+----------------------------------------+---------------------------------------------+
| id              | random integer                         | uniquely identifies the entry in the domain |
+-----------------+----------------------------------------+---------------------------------------------+
| origin          | 0                                      | Points to the parent or the channel/folder. |
+-----------------+----------------------------------------+---------------------------------------------+
| timestamp       | current discrete_clock value           |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| infohash        | assigned randomly                      |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| size            | 0                                      |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| torrent_date    | current datetime                       |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| title           | given by the user                      | indexed by FTS                              |
+-----------------+----------------------------------------+---------------------------------------------+
| tags            |                                        |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| tracker_info    |                                        |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| num_entries     | 0                                      |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| start_timestamp | same as timestamp                      |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| signature       | generated with the host's private key  |                                             |
|                 | from all the serialized fields (above) |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| status          | NEW                                    |                                             |
+-----------------+----------------------------------------+---------------------------------------------+
| local_version   | same as timestamp                      |                                             |
+-----------------+----------------------------------------+---------------------------------------------+

Note that ``discrete_clock`` is increased by +1 after each usage.

Torrent metadata entry creation
-------------------------------

The user adds a torrent to Tribler by creating a ``TorrentMetadata`` entry in the database:

+---------------+--------------------------------------------+
| Property      | Value                                      |
+===============+============================================+
| metadata_type | 300 (REGULAR_TORRENT)                      |
+---------------+--------------------------------------------+
| flags         | 0                                          |
+---------------+--------------------------------------------+
| public_key    | host's public key                          |
+---------------+--------------------------------------------+
| id            | random integer                             |
+---------------+--------------------------------------------+
| origin        | the id of the parent channel               |
+---------------+--------------------------------------------+
| timestamp     | current discrete_clock value               |
+---------------+--------------------------------------------+
| infohash      | assigned from the provided torrent         |
+---------------+--------------------------------------------+
| size          | assigned from the provided torrent         |
+---------------+--------------------------------------------+
| torrent_date  | assigned from the provided torrent         |
+---------------+--------------------------------------------+
| title         | assigned from the provided torrent         |
+---------------+--------------------------------------------+
| tags          | Text-based "category" of the torrent,      |
|               | assigned by analyzing the contents         |
|               | from the provided torrent                  |
+---------------+--------------------------------------------+
| tracker_info  | assigned from the torrent provided by user |
+---------------+--------------------------------------------+
| signature     | generated with the host's private key      |
|               | from all the serialized fields (above)     |
+---------------+--------------------------------------------+
| status        | NEW                                        |
+---------------+--------------------------------------------+


.. _channel_commit:

Committing the channel contents to disk
---------------------------------------
The basic idea of "commit" is to represent the *changes* to the channel tree as a stream
of data, serialize that stream, compress it, break down into files, add the files to the existing
channel directory, update the channel torrent from it, then update and re-sign the toplevel channel
entry with the infohash of the updated channel torrent.



.. _lz4_stream:

* After the GUI (or the user directly) initializes the commit channel action,
  the Metadata Store scans the domain of the host's public key for entries
  in the ``NEW``, ``UPDATED`` or ``DELETED`` status.
* For every new/updated entry, the Core builds the path from the entry to its root
  channel (the channel with ``origin_id==0``).
* New/updated entries are sorted by timestamp.
* Folder entries on the path to the channel root are updated with new counts of torrents in them (``num_entries``),
  recursively. These receive a new ``timestamp``s from ``discrete_clock`` and signature. Their ``status`` is changed
  to ``UPDATED``.
* All the ``UPDATED`` and ``NEW`` entries in the channel are serialized and concatenated
  into a single stream, that is incrementally compressed with `lz4 algorithm <https://en.wikipedia.org/wiki/LZ4_(compression_algorithm)>`_ and split into
  1 MB-sized chunks called mdblobs. The compression is performed incrementally, until the compressed mdblob size
  fits in 1 MB. Every blob is individually lz4-unpackable.
* The mdblobs are written into the channel's directory that is located at
  ``.Tribler/<version>/channels/<first 32 characters of hexlified public key><hexademical representation of channel's id padded to 16 characters>``
  (``hexlify(public_key)[:32] + "{:0>16x}".format(id)``)
* Afterwards, the mdblob is dumped into a new file in the channel's directory.
  The filename follows the pattern ``<last_metadata_entry's_timestamp>.mdblob.lz4``.
* The ``DELETE`` entries require special treatment. For each metadata entry marked ``DELETE``,
  a ``DeletedMetadataPayload`` is created with its ``delete_signature`` field containing
  the signature of the metadata entry to be deleted. Due to a design mistake, these payloads got
  no ``timestamp`` field. This resulted in a nasty error in those cases when a ``DELETE`` entry would
  be placed the last in an mdblob file. As a workaround, the ``DELETE`` entries are now serialized
  *last* in the stream, but whenever an mdblob file ends with such an entry, the it gets the filename
  from a ``discrete_clock`` tick.
* When all the changes are dumped to the disk, Metadata Store calls Libtorrent to create a torrent
  from the channel directory to obtain the new infohash.
* The toplevel channel entry is updated with the new ``infohash``, ``num_entries``, ``size``,
  and a ``timestamp`` from the ``discrete_clock`` tick. The entry's ``signature`` is updated accordingly.
* If the whole commit procedure finishes without errors, all the newly serialized entries change
  their status to ``COMMITTED``.

Delivering the channel entry to another host
-----------------------------------------------------
A channel entry can end up at another host in multiple ways, most of which involve
GigaChannel or RemoteQuery community:
* A search query through GigaChannel community can net a channel entry
* A channel entry can be queried by RemoteQuery community walking an querying for subscribed channels
* A channel entry can be gossiped by GigaChannel community (along with some preview contents).

Initially, when a host receives an unknown Channel entry, it will set its ``local_version`` to ``0``.
Whenever a host receives a channel entry with the same public key and id as it already know, but with a higher timestamp
it will update the entry with the data from the new one. If a channel is subscribed by user and
its ``local_version`` is lower that its ``timestamp``, GigaChannelManager will initiate the process of
downloading/processing the channel. Note that ``local_version`` and other local properties are *not*
overwritten by updating the channel entry. Only ``non-local`` (i.e. payload-serialized) attributes are updated.


Processing the channel from disk
--------------------------------
After the channel torrent was downloaded by GigaChannel Manager, the processing procedure is initiated.

* Processing is performed by sequentially reading the next mdblob file that has a filename/number that is higher than
  the current ``local_timestamp`` of the processed channel.
* ``start_timestamp`` puts the lower bound on the mdblob's names/timestamps that should be processed.
  Its main purpose is enabling the possibility of ``defragmentation`` or ``complete reset`` of a channel.
* All the metadata entries in each processed mdblob are unpacked, deserialized,
  checked for correct signature and added to the database
  *the same way as if they were received from network* (e.g. trough a query in by RemoteQuery community)
* As soon as the mdblob file processing is finished, the channel's ``local_version`` is set to the filename number.
  This guarantees that if processing is interrupted by e.g. a power fail, processing will restart from the same mdblob.
* The last mdblob's filename is equal to the channel's ``timestamp``. Therefore, as soon as the last
  mdblob is processed, the channel's ``local_version`` becomes equal to its ``timestamp``, thus
  putting the channel to "Complete" state.


Free-for-all metadata entries
-----------------------------

Free-for-all (FFA) metadata entry is a special kind of *unsigned* metadata entry. It is impossible to attribute such
an entry to any particular host, because the entry contain no traces of the host that created them. In other words,
given one torrent file, two different hosts will independently create the same FFA entry.

FFA entries are created whenever the user downloads a torrent that is unknown to MDS. Whenever MDS receives
a FFA entries are not attributed to any channel. Whenever MDS receives a signed metadata entry that has the same
infohash as an FFA entry, it will remove the FFA entry. FFA entries exist for the reason of
helping local and remote keyword search.


















