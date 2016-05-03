package org.tribler.android;

/**
 * Deserialization of Json Content
 */
public class AbstractContent {
    private String title;
    private String image_url;
    private String description;

    public String getTitle() {
        return title;
    }

    public String getImage_url() {
        return image_url;
    }

    public String getDescription() {
        return description;
    }

    public AbstractContent() {
    }
}
