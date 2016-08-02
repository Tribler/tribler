package org.tribler.android.restapi.json;

public class TriblerChannel {

    private boolean subscribed;
    private int id, votes, torrents, spam, modified;
    private String dispersy_cid, name, description, icon_url;

    TriblerChannel() {
    }

    public void setSubscribed(boolean subscribed) {
        this.subscribed = subscribed;
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
        return icon_url;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean equals(Object object) {
        if (this == object) {
            return true;
        }
        if (object == null || getClass() != object.getClass()) {
            return false;
        }
        TriblerChannel that = (TriblerChannel) object;
        if (dispersy_cid == null) {
            return that.dispersy_cid == null;
        }
        return dispersy_cid.equals(that.dispersy_cid);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int hashCode() {
        return dispersy_cid.hashCode();
    }

}
