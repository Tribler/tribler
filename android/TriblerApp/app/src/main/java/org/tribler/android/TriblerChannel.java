package org.tribler.android;

/**
 * Deserialization of JSON channel
 */
public class TriblerChannel {

    private boolean subscribed;
    private int id, votes, torrents, spam, modified;
    private String dispersy_cid, name, description, icon_url;

    public TriblerChannel() {
    }

    public boolean isSubscribed() {
        return subscribed;
    }

    public int getId() {
        return id;
    }

    public int getVotesCount() {
        return votes;
    }

    public int getTorrentsCount() {
        return torrents;
    }

    public int getSpamCount() {
        return spam;
    }

    public int getModified() {
        return modified;
    }

    public String getDispersyCid() {
        return dispersy_cid;
    }

    public String getName() {
        return name;
    }

    public String getDescription() {
        return description;
    }

    public String getIconUrl() {
        if (icon_url == null) {
            icon_url = ""; //TODO: default image
        }
        return icon_url;
    }

}
