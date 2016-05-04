package org.tribler.android;

/**
 * Deserialization of Json Channel
 */
public class TriblerChannel {
    private String name;
    private String iconUrl;
    private int videosCount;
    private int commentsCount;

    public TriblerChannel() {
    }

    public String getName() {
        return name;
    }

    public String getIconUrl() {
        return iconUrl;
    }

    public int getVideosCount() {
        return videosCount;
    }

    public int getCommentsCount() {
        return commentsCount;
    }

}
