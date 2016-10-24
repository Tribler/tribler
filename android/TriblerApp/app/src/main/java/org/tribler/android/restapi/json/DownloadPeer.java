package org.tribler.android.restapi.json;

public class DownloadPeer {

    private String ip, wstate;
    private double dtotal, downrate;
    private boolean uninterested, optimistic;

    DownloadPeer() {
    }

    public String getIp() {
        return ip;
    }

    public String getWState() {
        return wstate;
    }

    public double getDTotal() {
        return dtotal;
    }

    public double getDownRate() {
        return downrate;
    }

    public boolean isUninterested() {
        return uninterested;
    }

    public boolean isOptimistic() {
        return optimistic;
    }

}
