package org.tribler.android.restapi.json;

public class DownloadTracker {

    private String url, status;
    private int peers;

    DownloadTracker() {
    }

    public String getUrl() {
        return url;
    }

    public String getStatus() {
        return status;
    }

    public int getPeers() {
        return peers;
    }

}
