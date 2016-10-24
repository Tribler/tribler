package org.tribler.android.restapi.json;

import java.util.List;

public class TorrentDiscoveredEvent {

    public static final String TYPE = "torrent_discovered";

    private String infohash, name, dispersy_cid;
    private List<List> files;
    private List<String> trackers;
    private int timestamp;

    TorrentDiscoveredEvent() {
    }

    public String getInfohash() {
        return infohash;
    }

    public String getName() {
        return name;
    }

    public List<List> getFiles() {
        return files;
    }

    public List<String> getTrackers() {
        return trackers;
    }

    public String getDispersyCid() {
        return dispersy_cid;
    }

    public int getTimestamp() {
        return timestamp;
    }

}
