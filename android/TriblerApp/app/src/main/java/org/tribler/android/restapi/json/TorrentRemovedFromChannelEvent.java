package org.tribler.android.restapi.json;

public class TorrentRemovedFromChannelEvent {

    public static final String TYPE = "torrent_removed_from_channel";

    private String infohash;
    private int channel_id;

    TorrentRemovedFromChannelEvent() {
    }

    public String getInfohash() {
        return infohash;
    }

    public int getChannelId() {
        return channel_id;
    }

}
