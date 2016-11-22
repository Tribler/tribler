package org.tribler.android.restapi.json;

public class StartedDownloadAck {

    private boolean started;
    private String infohash;

    StartedDownloadAck() {
    }

    public boolean isStarted() {
        return started;
    }

    public String getInfohash() {
        return infohash;
    }

}
