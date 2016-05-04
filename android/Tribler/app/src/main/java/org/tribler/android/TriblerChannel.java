package org.tribler.android;

/**
 * Deserialization of Json Channel
 */
public class TriblerChannel {
    private String name, iconUrl;
    private int torrentsCount, commentsCount;

    public TriblerChannel() {
    }

    public String getName() {
        return name;
    }

    public String getIconUrl() {
        if (iconUrl == null) {
            iconUrl = ""; //TODO: default image
        }
        return iconUrl;
    }

    public int getTorrentsCount() {
        return torrentsCount;
    }

    public int getCommentsCount() {
        return commentsCount;
    }

}
