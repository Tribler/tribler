package org.tribler.android.restapi.json;

import java.util.List;

public class TriblerDownload {

    private String name, infohash, destination;
    private double progress, speed_down, speed_up, availability;
    private long size, max_upload_speed, max_download_speed;
    private int eta, num_peers, num_seeds, hops, total_pieces;
    private boolean anon_download, safe_seeding;
    private List<DownloadFile> files;
    private List<DownloadTracker> trackers;
    private List<DownloadPeer> peers;

    TriblerDownload() {
    }

    public String getName() {
        return name;
    }

    public String getInfohash() {
        return infohash;
    }

    public String getDestination() {
        return destination;
    }

    public double getProgress() {
        return progress;
    }

    public double getSpeedDown() {
        return speed_down;
    }

    public double getSpeedUp() {
        return speed_up;
    }

    public double getAvailability() {
        return availability;
    }

    public long getSize() {
        return size;
    }

    public long getMaxUploadSpeed() {
        return max_upload_speed;
    }

    public long getMaxDownloadSpeed() {
        return max_download_speed;
    }

    public int getEta() {
        return eta;
    }

    public int getNumPeers() {
        return num_peers;
    }

    public int getNumSeeds() {
        return num_seeds;
    }

    public int getHops() {
        return hops;
    }

    public int getTotalPieces() {
        return total_pieces;
    }

    public boolean isAnonDownload() {
        return anon_download;
    }

    public boolean isSafeSeeding() {
        return safe_seeding;
    }

    public List<DownloadFile> getFiles() {
        return files;
    }

    public List<DownloadTracker> getTrackers() {
        return trackers;
    }

    public List<DownloadPeer> getPeers() {
        return peers;
    }

}

