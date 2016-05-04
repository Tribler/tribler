package org.tribler.android;

/**
 * Deserialization of Json Channel
 */
public class TriblerChannel {
    private String name, iconUrl;
    private int videosCount, commentsCount;

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

    public int getVideosCount() {
        return videosCount;
    }

    public int getCommentsCount() {
        return commentsCount;
    }

}
