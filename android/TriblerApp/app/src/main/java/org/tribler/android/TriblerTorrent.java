package org.tribler.android;

/**
 * Deserialization of JSON Torrent
 */
public class TriblerTorrent {

    private String title, thumbnailUrl;
    private int duration, bitrate;

    public TriblerTorrent() {
    }

    public String getTitle() {
        return title;
    }

    public String getThumbnailUrl() {
        if (thumbnailUrl == null) {
            thumbnailUrl = ""; //TODO: default image
        }
        return thumbnailUrl;
    }

    public int getDuration() {
        return duration;
    }

    public int getBitrate() {
        return bitrate;
    }

}
