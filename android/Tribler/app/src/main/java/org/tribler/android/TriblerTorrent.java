package org.tribler.android;

/**
 * Deserialization of Json Torrent
 */
public class TriblerTorrent {
    private String title;
    private String thumbnailUrl;
    private int duration;
    private int bitrate;

    public TriblerTorrent() {
    }

    public String getTitle() {
        return title;
    }

    public String getThumbnailUrl() {
        return thumbnailUrl;
    }

    public int getDuration() {
        return duration;
    }

    public int getBitrate() {
        return bitrate;
    }

}
