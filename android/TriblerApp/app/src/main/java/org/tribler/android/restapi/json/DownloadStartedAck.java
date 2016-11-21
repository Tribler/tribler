package org.tribler.android.restapi.json;

public class DownloadStartedAck {

    private boolean started;
    private String infohash;

    DownloadStartedAck() {
    }

    public boolean isStarted() {
        return started;
    }

    public String getInfohash() {
        return infohash;
    }

}
