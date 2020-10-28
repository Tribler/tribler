This document briefly describes the main ideas and design decisions behind the Channels 2.0 (GigaChannels) system.

Channels architecture
=====================

In Tribler, users can share their torrents collection by creating a "Channel" (*a la* Youtube)
and adding some torrents to it.
The channel and its contents will then be shown to other Tribler users in the common list of
"Discovered" channels. Users can keyword search channels for content.
Channels popularity rating helps users identify quality content.

Basically, Channels 2.0 works by spreading gossip about available channels, downloading channels "subscribed"
by the user and putting them into the local channels database (`Metadata Store`_).
When subscribed, channels are transferred through Libtorrent.
The infohashes linking to these "channel torrents" are sent around by specialized IPv8 communities
(`GigaChannel Community`_ and `RemoteQuery Community`_). Each metadata entry is individually signed by its author's
private key, preventing other users from modifying other's channels.
The user can create multiple channels with a tree of internal "folders".
Channels and metadata entries can be updated or deleted by their author.


The Channels system consists of a number of disparate, complementary subsystems:

* `Metadata Store`_
* `GigaChannel Manager`_
* `GigaChannel Community`_
* `RemoteQuery Community`_
* `VSIDS heuristics`_ for channels popularity


What is a channel?
------------------

A *channel* is a collection of *signed* metadata entries. These entries form a forest of channel/folder(collection)
trees. Every metadata entry contains an id, a timestamp and a pointer to the id of its parent channel/folder.
Every metadata entry is individually signed by the creator host's private key. The signature is included
in the serialized form of the entry, along with the public key. This allows the entries to be trustfully spread
through a network of untrusting strangers, if all of them trust the entry creator's public key.

A channel exists in two forms:

* a set of DB entries in a PonyORM-backed SQLite DB (*The DB form*).
* a stream of serialized entries broken down into :ref:`lz4-packed chunks<lz4_stream>`
  dumped into files in a torrent (*the Torrent form*).


A channel entry is added to the local DB only if it passes the "logical firewall" with strict criteria for
correctness (e.g. signature check, etc.). This is true for no matter the way an entry enters the system, be it
from the torrent form, or from any kind of network packet.

* A user can have an arbitrary number of channels in the "domain" of his or her public key.
* A channel can have an arbitrary number of nested folders/metadata entries.


Detailed description of the serialization ("Commit") process and serialization formats
used by Channels system can be found in the following documents:

.. toctree::
  :maxdepth: 2

  channel_torrent_storage_format
  serialization_format

Metadata Store
------------------

The Metadata Store (MDS) consists of:

* PonyORM bindings (class definitions)
* methods for converting channels between DB and Torrent forms.

The process of dumping a channel to a torrent is called a "commit", because it creates a serialized
snapshot of the channel. For details, see the documentation on :ref:`channel torrent storage<channel_commit>`.


GigaChannel Manager
-----------------------

The GigaChannel Manager (GM) is responsible for downloading channel torrents and processing them into MDS.
GM regularly queries MDS and Tribler Download Manager for state changes and starts required actions:

* for subscribed channels that must be downloaded or updated GM starts downloading the corresponding torrents;
* for already downloaded channel torrents GM starts processing them into MDS;
* GM deletes old channel torrents that does not belong to any channel.

Internally, GM uses a queue of actions. GM queue tries to be smart and only do the necessary operations
For instance, if the user subscribes to a channel, then immediately unsubscribes from
it, and then subscribes to it again, the channel will only be downloaded once.

The looping task + actions queue design is necessary to prevent the callback / race condition nightmare of synchronizing
Libtorrent's and ``asyncio``'s reactors.

GigaChannel Community
-------------------------

The GigaChannel Community (GC) is the original channels gossip/search overlay deployed with the first implementation
of Channels 2.0. It plays the following roles:

* spreading push-based gossip of subscribed channels, along with some preview contents;
* sending and serving remote keyword search queries (initiated by searching for stuff in the Tribler GUI).


Channel gossip
~~~~~~~~~~~~~~

At regular intervals, GC queries MDS for a random subscribed channel and
assembles a "preview blob" containing the channel metadata entry and some of its contents.
GC then sends this preview blobs to random peers in push-based gossip.

Keyword search
~~~~~~~~~~~~~~

When the user initiates a keyword search, GS sends a request to a number of the host's random peers.
The remote hosts respond to these requests with serialized metadata entries.
Upon receiving a response, calls MDS to process them. Then:

* if the received entries were already known, nothing happens;
* if the received entries are new entries or updated version of already known entries,
  these will be added to MDS and shown to user through the GUI;
* if local MDS happens to have newer versions of some of the received entries, GC will send the newer
  entries back as a gratuitous update.
  ("Hey buddy, that's old news! I got a newer version of the stuff you gave me. Here, take it for free.)


GigaChannel Community is supposed to be superseded by the more robust RemoteQuery Community.

RemoteQuery Community
-------------------------

The RemoteQuery Community (RQC) essentially provides a way to query remote hosts' MDS
with the same multi-purpose ``get_entries`` method that is used by the local ``metadata`` REST endpoint.
While looking dangerous on the surface (hello, SQL injection!), it only allows for very limited types of ``SELECT``-like
queries. The philosophy of RQC is that it never allows to get more information from the host
that is not already exposed by the network through other means (e.g. GigaChannel Community).
RQC plays the following roles:

* Pulling subscribed channels from other host during endless walk. This allows for fast bootstrapping Channel
  contents on new clients.
* Providing a generic mechanism for exchanging metadata info between hosts.
* Enabling researches to gather useful statistics from metadata-gathering walks.

VSIDS heuristics
----------------

VSIDS stands for Variable State Independent Decaying Sum heuristic. Its basic idea is that the "weight"
of some element additively increases on each access to that element, but multiplicatively decreases (decays)
over time. VSIDS is close to timed PageRank in its results in the sense it selects variables with
high temporal degree centrality and temporal eigenvector centrality (see. "Understanding VSIDS Branching Heuristics
in Conflict-Driven Clause-Learning SAT Solvers" by Jia Hui Liang et. al.).

We use VSIDS to calculate the channel popularity. Whenever a channel is received by RQC or GC,
its rating is bumped additively. Over the time, channels ratings decay in such a way, that a channel's rating
is reduced 2.78 times over 3 days. As a classic optimization, instead of decaying all the channel entries all the time,
we increase the bump amount proportionally. The implementation also includes standard VSIDS features
such as normalization and float overflow protection/renormalization.
An important detail of our implementation is that the a single host can never bump the channel more than once.
Instead, it can only "renew" its vote. This is achieved by storing the last vote for each host/channel pair
along with its bump amount, and deducting it from the channel vote rating before applying the vote again,
with the current bump amount.

VSIDS is implemented as a part of MDS.














