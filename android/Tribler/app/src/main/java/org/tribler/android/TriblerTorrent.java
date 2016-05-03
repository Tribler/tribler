package org.tribler.android;

/**
 * Deserialization of Json Torrent
 */
public class TriblerTorrent extends AbstractContent {
    private int duration;
    private int bitrate;

    public int getDuration() {
        return duration;
    }

    public int getBitrate() {
        return bitrate;
    }

    public TriblerTorrent() {
    }
}
