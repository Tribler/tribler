package org.tribler.android;

/**
 * Deserialization of JSON Torrent
 */
public class TriblerTorrent {

    private String name, category, thumbnailUrl;
    private int duration, bitrate;

    public TriblerTorrent() {
    }

    public String getName() {
        return name;
    }

    public String getCategory() {
        return category;
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
