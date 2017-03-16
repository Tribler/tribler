# Aufbau

![Structural View](../Resources/Structure_Diagram.png)

| Ordner                                            | Unterordner                                                   | Beschreibung   |
|---------------------------------------------------|---------------------------------------------------------------|---------------|
| [Category](/Tribler/Category)                     | -                                                             | Beinhaltet Code um Torrents zu kategorisieren und die Kategorien entsprechend der Filtereinstellungen zu filtern.               |
| [Core](/Tribler/Core)                             | -                                                             | Beinhaltet die Kern-Funktionalitäten des Tribler-Projekts.                                                     |
|                                                   | [APIImplementation](/Tribler/Core/APIImplementation)          | Beinhaltet die API für Torrents um diese zu erstellen und zu verwalten.             |
|                                                   | [CacheDB](/Tribler/Core/CacheDB)                              | Beinhaltet die zwischengespeicherte Datenbank für Tribler, welche die verschiedenen Versionen verwaltet und einen Notifier beinhaltet.              |
|                                                   | [DecentralizedTracking](/Tribler/Core/DecentralizedTracking)  | Beinhaltet die pymdht Bibliothek um Netzwerk Informationen anzuzeigen.              |
|                                                   | [Libtorrent](/Tribler/Core/Libtorrent)                        | Beinhaltet den Code um die Torrent-Bibliothek zu verwalten.              |
|                                                   | [Modules](/Tribler/Core/Modules)                              | Beinhaltet den Tracker-Manager.              |
|                                                   | [RawServer](/Tribler/Core/RawServer)                          | Beinhaltet den Raw-Server inklusive eines Socket-Handlers und eines Polling-Systems.              |
|                                                   | [TFTP](/Tribler/Core/TFTP)                                    | Beinhaltet den TFTP-Handler, welcher am Raw-Server registriert sein sollte um TFTP-Pakete zu verarbeiten.              |
|                                                   | [TorrentChecker](/Tribler/Core/TorrentChecker)                | Beinhaltet den Code, welcher Torrents überprüft.              |
|                                                   | [Upgrade](/Tribler/Core/Upgrade)                              | Beinhaltet Informationen wie Tribler und die Datenbank geupdatet wird.              |
|                                                   | [Utilities](/Tribler/Core/Utilities)                          | Beinhaltet verschiedene Utility-Files, die im Projekt genutzt werden.              |
|                                                   | [Video](/Tribler/Core/Video)                                  | Beinhaltet den VLCWrapper und den Code um Livestreams über Tribler ermöglichen.              |
| [Community](/Tribler/community)                   | -                                                             | Beinhaltet den Code um sicher mit anderen Communities zu kommunizieren.              |
|                                                   | [allchannel](/Tribler/community/allchannel)                   | Beinhaltet den Code für eine einzige Community, der alle Tribler-Benutzer beitreten und benutzen um .torrent Dateien auszutauschen.              |
|                                                   | [channel](/Tribler/community/channel)                         | ???              |
|                                                   | [demers](/Tribler/community/demers)                           | ???              |
|                                                   | [metadata](/Tribler/community/metadata)                       | ???              |
|                                                   | [search](/Tribler/community/search)                           | ???              |
|                                                   | [template](/Tribler/community/template)                       | Beinhaltet Beispiel-Dateien für die Communities.              |
|                                                   | [tunnel](/Tribler/community/tunnel)                           | Definiert eine Proxy-Community, welche andere Proxy-Server aufspührt und eine API bereitstellt um Reverse-Circuits zu erstellen.              |
| [Debug](/Tribler/Debug)                           | -                                                             | Beinhaltet Code um Tribler zu debuggen.              |
| [Dispersy](https://github.com/Tribler/dispersy)   | -                                                             | Erweiterbares Datenbank-System, das das Rückgrat der Funktionalität von Tribler darstellt.       |
| [Main](/Tribler/Main)                             | -                                                             | Beinhaltet den Code für die Grafische Ausgabe von Tribler.              |
|                                                   | [Build](/Tribler/Main/Build)                                  | Beinhaltet Build-Files für verschiedene Betriebssysteme.              |
|                                                   | [Dialogs](/Tribler/Main/Dialogs)                              | Beinhaltet die verschiedenen Dialoge, welche innerhalb von Tribler gezeigt werden.              |
|                                                   | [Utility](/Tribler/Main/Utility)                              | Beinhaltet verschiedene Utility-Klassen, die im Main-Package benutzt werden.              |
|                                                   | [vwxGUI](/Tribler/Main/vwxGUI)                                | Beinhaltet den Code für die (non-browser) GUI von Tribler.               |
|                                                   | [webUI](/Tribler/Main/webUI)                                  | Beinhaltet den Code um eine Benutzeroberfläche zu erstellen, welche in einem Browser geöffnet werden kann.              |
| [Policies](/Tribler/Policies)                     | -                                                             | Beinhaltet den Code für Bewertungs- und Seeding-Richtlinien in Tribler.              |
| [Test](/Tribler/Test)                             | -                                                             | Beinhaltet Testfunktionalitäten für Tribler.              |
|                                                   | [API](/Tribler/Test/API)                                      | Beinhaltet Tests für die API.              |
|                                                   | [data](/Tribler/Test/data)                                    | Beinhaltet Daten, die für Tests benötgt werden.              |
| [Utilities](/Tribler/Utilities)                   | -                                                             | Beinhaltet veschiedene Utility-Klassen, die in Tribler benutzt werden.               |
| [twisted](https://github.com/twisted)             | -                                                             | Event Driven Networking Engine        |

#### Wartung
Innerhalb des [Resources](../Resources)-Ordners ist eine .xml Datei, welche in [Draw.io](https://www.draw.io) geöffnet werden kann und die Möglichkeit besteht diese bei Bedarf zu bearbeiten.
