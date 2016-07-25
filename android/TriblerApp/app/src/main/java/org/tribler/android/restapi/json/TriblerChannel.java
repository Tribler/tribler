package org.tribler.android.restapi.json;

import java.io.Serializable;

public class TriblerChannel implements Serializable {

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

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        TriblerChannel that = (TriblerChannel) o;

        if (subscribed != that.subscribed) return false;
        if (id != that.id) return false;
        if (votes != that.votes) return false;
        if (torrents != that.torrents) return false;
        if (spam != that.spam) return false;
        if (modified != that.modified) return false;
        if (!dispersy_cid.equals(that.dispersy_cid)) return false;
        if (name != null ? !name.equals(that.name) : that.name != null) return false;
        if (description != null ? !description.equals(that.description) : that.description != null)
            return false;
        return icon_url != null ? icon_url.equals(that.icon_url) : that.icon_url == null;

    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int hashCode() {
        return dispersy_cid.hashCode();
    }
}
