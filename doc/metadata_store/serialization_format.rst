This document contains information about serialization format used by Metadata Store
to serialize metadata entries before sending them over the network and saving them on disk

Payload types and serialization formats
=======================================
All payloads follow the same pattern:

serialized parent metadata type + type specific data  + signature.

Payload field types are expressed in
`Python Struct notation <https://docs.python.org/2/library/struct.html>`_.

Metadata types are identified by integers as follows:

+-----------------+------------------------+-----------------+------------------------+
|     ORM type    |      Payload type      | Python constant | Numeric metadata type  |
+=================+========================+=================+========================+
|                 |                        | TYPELESS        |         100            |
+-----------------+------------------------+-----------------+------------------------+
| ChannelNode     | ChannelNodePayload     | CHANNEL_NODE    |         200            |
+-----------------+------------------------+-----------------+------------------------+
| MetadataNode    | MetadataNodePayload    | METADATA_NODE   |         210            |
+-----------------+------------------------+-----------------+------------------------+
| CollectionNode  | CollectionNodePayload  | COLLECTION_NODE |         220            |
+-----------------+------------------------+-----------------+------------------------+
| TorrentMetadata | TorrentMetadataPayload | REGULAR_TORRENT |         300            |
+-----------------+------------------------+-----------------+------------------------+
| ChannelMetadata | ChannelMetadataPayload | CHANNEL_TORRENT |         400            |
+-----------------+------------------------+-----------------+------------------------+
|                 | DeletedMetadataPayload | DELETED         |         500            |
+-----------------+------------------------+-----------------+------------------------+


SignedPayload
-------------
This is the base class/payload type. It is never used on the wire "as is" and should only be used as
a parent class for other payloads.

- The signature is applied to the end of the serialized payload.
- ``flags`` field is reserved for future use.
- Public key and signature use LibNaCl Curve25519 ECC.
- If both the signature and public key are all-zeroes, the payload is a "Free-for-All" (FFA) metadata entry.

+---------------+------------------+------------+-----------+
| Metadata type | Flags (reserved) | Public key | Signature |
+---------------+------------------+------------+-----------+
|       H       |         H        |     64s    |    64s    |
+---------------+------------------+------------+-----------+
|                      Signed                   |           |
+-----------------------------------------------+-----------+


ChannelNodePayload
------------------
This is another "virtual" class/payload type. It represents an abstract node in
the channel internal hierarchy graph.

- ``id`` is a random integer which, together with the public key,
  uniquely identifies the ChannelNode in the Channels system.
- ``origin`` is the ``id`` of the parent ChannelNode. ``0`` in this field means a top-level, parentless entry.
- ``timestamp`` stands for the "creation time" of this ChannelNode.
  Typically, it contains the value from the monotonically increasing discrete clock-like counter `DiscreteClock`
  in the MetadataStore.

+---------------+------------------+------------+----+--------+-----------+-----------+
| Metadata type | Flags (reserved) | Public key | Id | Origin | Timestamp | Signature |
+---------------+------------------+------------+----+--------+-----------+-----------+
|       H       |         H        |     64s    |  Q |    Q   |     Q     |    64s    |
+---------------+------------------+------------+----+--------+-----------+-----------+


MetadataNodePayload
-------------------
This is a generic "virtual" metadata-containing node in the channels graph.

- ``title`` field contains the entry's title, e.g. a name for a movie or a title for a torrent.
  It is indexed by FTS in MetadataStore.
- ``tags`` field is reserved for human-readable tags usage. It is **not** indexed by FTS.
  Currently, the first word in this field is interpreted as the entry's category.
  For ChannelTorrent entries, it contains channel description (for reasons of the legacy Channels system compatibility).

+---------------+------------------+------------+----+--------+-----------+---------+---------+-----------+
| Metadata type | Flags (reserved) | Public key | Id | Origin | Timestamp | Title   | Tags    | Signature |
+===============+==================+============+====+========+===========+=========+=========+===========+
|       H       |         H        |     64s    |  Q |    Q   |     Q     | varlenI | varlenI |    64s    |
+---------------+------------------+------------+----+--------+-----------+---------+---------+-----------+

TorrentMetadataPayload
----------------------
This is the primary type of payloads used in the Channels system - a payload for BitTorrent metadata.

- ``infohash`` stands for BitTorrent infohash, in binary form.
- ``size`` stands for the torrent size in bytes.
- `torrent_date` stands for the torrent creation date, in seconds since Unix Epoch.
- `tracker_info` is the tracker URL
- Note that this payload inherits directly from ChannelNodePayload, and **not** from MetadataNodePayload.
  The title and tags field are moved to the end of the payload (for a dumb reason of micro-optimizing deserialization).


+---------------+------------------+------------+----+--------+-----------+----------+------+--------------+---------+---------+--------------+-----------+
| Metadata type | Flags (reserved) | Public key | Id | Origin | Timestamp | Infohash | Size | Torrent date | Title   | Tags    | Tracker info | Signature |
+===============+==================+============+====+========+===========+==========+======+==============+=========+=========+==============+===========+
|       H       |         H        |     64s    |  Q |    Q   |     Q     |    20S   |   Q  |       I      | varlenI | varlenI |    varlenI   |    64s    |
+---------------+------------------+------------+----+--------+-----------+----------+------+--------------+---------+---------+--------------+-----------+


CollectionNodePayload
---------------------
This payload serializes CollectionNode entries, which are like ChannelTorrent entries, but w/o infohash field.
CollectionNode entries are used to represent intra-channel "folders" of torrents and/or other folders.

- ``num_entries`` field represents the number of entries that is contained in this Collection and its sub-collections.



+---------------+------------------+------------+----+--------+-----------+---------+---------+-------------+-----------+
| Metadata type | Flags (reserved) | Public key | Id | Origin | Timestamp | Title   | Tags    | Num entries | Signature |
+===============+==================+============+====+========+===========+=========+=========+=============+===========+
|       H       |         H        |     64s    |  Q |    Q   |     Q     | varlenI | varlenI |      Q      |    64s    |
+---------------+------------------+------------+----+--------+-----------+---------+---------+-------------+-----------+

ChannelMetadataPayload
----------------------
This payload serializes ChannelTorrent entries, combining properties of CollectionNodePayload,
and TorrentMetadataPayload.

- ``start_timestamp`` represents the first timestamp in this channel.
  It is used to limit the channel's span back in time after e.g. defragmenting a channel or restarting it anew.
- ``torrent_date`` is used by the GUI to show when the channel was committed the last time (the "Updated" column).

+---------------+------------------+------------+----+--------+-----------+----------+------+--------------+---------+---------+--------------+-------------+-----------------+-----------+
| Metadata type | Flags (reserved) | Public key | Id | Origin | Timestamp | Infohash | Size | Torrent date | Title   | Tags    | Tracker info | Num entries | Start timestamp | Signature |
+===============+==================+============+====+========+===========+==========+======+==============+=========+=========+==============+=============+=================+===========+
|       H       |         H        |     64s    |  Q |    Q   |     Q     |    20s   |   Q  |       I      | varlenI | varlenI |    varlenI   |      Q      |        Q        |    64s    |
+---------------+------------------+------------+----+--------+-----------+----------+------+--------------+---------+---------+--------------+-------------+-----------------+-----------+


DeletedMetadataPayload
----------------------
This payload is a "command" for the Channels system to delete an entry.
The entry to delete is pointed by its signature.

- Currently, this metadata can only exist in serialized form. It is never saved to DB.
- ``delete_signature`` the signature of the metadata entry to be deleted.

+---------------+------------------+------------+------------------+-----------+
| Metadata type | Flags (reserved) | Public key | Delete signature | Signature |
+---------------+------------------+------------+------------------+-----------+
|       H       |         H        |     64s    |    64s           |    64s    |
+---------------+------------------+------------+------------------+-----------+


HealthItemsPayload
------------------

+---------+
| Data    |
+=========+
| varlenI |
+---------+

The optional health information is serialized separately, as it was not originally included in the serialized
metadata format. The payload consists of a single field with ascii-encoded string which encodes zero or many items.
If present, it should contain the same number of items as the serialized list of metadata entries.
The N-th health info item in the health block corresponds to the N-th metadata entry.

The health info string format has the following properties:

- Binary data for items can be added in an incremental way (unlike, for example, JSON). This is convenient when
  trying to fit as many entries as possible into a limited-size IPv8 packet.
- It is forward-compatible (unlike some binary formats): in the future, it is possible to extend it with new fields.
- It is compact: most entries are 1 byte.
- It is simple and human-readable.

Health item format description:

- Data format: utf-8 encoded text.
- Items separator: each item ends with a semicolon ``;``. Items MUST NOT contain semicolons inside.
- Fields separator: an item consists of fields separated by comma ``,``. Only the first three fields are currently
  parsed, and the rest are ignored. In the future, it is possible to add more fields to this list.
- Fields interpretaion: the first three fields are parsed as int values:

  - number of seeders,
  - number of leechers,
  - last_check timestamp.

- Empty item: an empty item (i.e. a single semicolon ``;``) means a default item with default field values, namely:

  - ``seeders=0``,
  - ``leechers=0``,
  - ``last_check=0``.


Examples
~~~~~~~~

- ``;;;;;``

  Five health info entries, each with seeders=0, leechers=0, last_check=0

- ``1,2,1234567;``

  A single health info entry with seeders=1, leechers=2, last_check=1234567

- ``;10,0,1234567;0,5,1234568;``

  Three health info items:

  - ``(seeders=0,leechers=0,last_check=0)``,
  - ``(seeders=10,leechers=0,last_check=1234567)``,
  - ``(seeders=0,leechers=5,last_check=1234568)``.

- ``10,20,1234567,foo,bar;``

  A single health info item ``(seeders=10, leechers=20, last_check=1234567)``. The ``"foo,bar"`` part is ignored.
