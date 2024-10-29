Software Architecture
=====================

This reference provides a high-level overview of Tribler's software architecture.

The main entry point of Tribler is the ``run_tribler.py`` script and it has two main modes.
The first mode launches Tribler with default settings.
This causes a new browser tab to open that displays a web page generated with TypeScript.
The second "headless" mode, does not open a browser tab.
However, in both modes the core Tribler Python process runs.

An overview of the most important functional components of Tribler is given in the following graph.
We will provide a short description of each of these components.

.. figure:: software_architecture.svg

Session
-------

The ``Session`` object (in ``session.py``) manages the core managers of Tribler:

- The ``Notifier`` allows components to publish and subscribe to events.
  In some special cases, this is preferred over class inheritance or composition.
  Architectural spaghetti can sometimes be avoided by using ``Notifier`` events.
- The ``TriblerConfigManager`` manages writing to and reading from user configuration files.
  This class manages defaults and the regeneration of (partially) missing configurations.
- The ``DownloadManager`` allows management of torrent downloads.
  Functionality involves fetching torrent meta information, adding and removing downloads, and changing their anonymity level.
- The ``RESTManager`` sets up a REST API.
  The API is used by Tribler's GUI, but can also be used programmatically by users in "headless" mode.
- ``IPv8`` is used to manage peer-to-peer network overlays.
  All peer-to-peer traffic is handled by ``IPv8`` with the exception of non-anonymized torrent downloads.
  Functionality involves decentralized search and sharing popular torrents.
- The ``IPv8CommunityLoader`` is used to launch all optional parts of Tribler.
  This includes launching ``IPv8`` overlays and registering REST API endpoints.

The ``TriblerDatabase``, ``MetadataStore`` and the ``TorrentChecker`` are optionally available through the ``Session``.
If requested, they are launched through the ``IPv8CommunityLoader``.

Components
----------

The optional components of Tribler are given in ``components.py``.
They can be divided into two groups: those that require a network overlay (inheriting from ``ComponentLauncher``) and those that do not (inheriting from ``ComponentLauncher``).
Furthermore, the components can have complex relationships, like only launching after other components.

The following list contains a high-level description of the components:

- The ``DatabaseComponent`` is responsible for the two main databases.
  The first is the ``MetadataStore``, which stores all torrent and torrent tracker meta data and "health" (seeders and leechers).
  The second is the ``TriblerDatabase``, which stores torrent tags.
- The ``TorrentCheckerComponent`` is responsible for retrieving the "health" information of torrents and trackers.
  This component may contact trackers for random torrents to determine whether they are reachable.
  The component also periodically updates the health information for known torrents based on tracker and DHT information.
- The ``VersioningComponent`` is responsible for Tribler version management.
  Functionality includes upgrading data from local old Tribler versions to new Tribler versions and determining whether a new Tribler version has been published online.
- The ``TunnelComponent`` allows for anonymization of torrent downloads.
  This component manages routing downloads over Tor-like circuits, including circuit construction and destruction.
- The ``DHTDiscoveryComponent`` allows ``IPv8`` to decentrally search for overlays and peers with given public keys.
- The ``ContentDiscoveryComment`` serves remote user searches and content popularity.
  Both outgoing and incoming user searches are served through this component.
- The ``KnowledgeComponent`` handles extraction and search for torrent tags.
- The ``RendezvousComponent`` keeps track of peers that have been connected to in the past.
  This is an experimental component that aims to serve as a source of decentral reputation.
- The ``RecommenderComponent`` keeps track of local user searches and the preferred download for the search query.
  This is an experimental component that aims to serve as a source for Artificial Intelligence based personalized recommendations.

Web UI
------

The Web UI serves to view and control the state of the Tribler process.
Essentially, the Web UI uses three main classes:

- The ``IPv8Service`` binds to the REST API of the ``IPv8`` component in the Tribler process.
- The ``TriblerService`` binds to the REST API of anything that is not in the ``IPv8`` service.
- The ``App`` is the React application entrypoint.

The ``App`` contains a component to route information, the ``RouterProvider``, and a means to report errors that have been sent from the Tribler process.
The architecture closely resembles the information in the GUI.
Essentially, the ``RouterProvider`` mirrors the visible pages:

- ``src/pages/Debug`` queries the Tribler process for debug information.
- ``src/pages/Downloads`` includes components to render torrent downloads.
- ``src/pages/Popular`` queries for popular torrents.
- ``src/pages/Search`` manages pending searches, combining local and remote results.
- ``src/pages/Settings`` reads and writes the Tribler configuration (through the REST API).