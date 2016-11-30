package org.tribler.android.restapi.json;

public class TriblerTorrent {

    private int id, num_seeders, num_leechers, last_tracker_check;
    private long size;
    private String infohash, name, category, thumbnail_url;

    TriblerTorrent() {
    }

    public int getId() {
        return id;
    }

    public long getSize() {
        return size;
    }

    public int getNumSeeders() {
        return num_seeders;
    }

    public int getNumLeechers() {
        return num_leechers;
    }

    public int getLastTrackerCheck() {
        return last_tracker_check;
    }

    public String getInfohash() {
        return infohash;
    }

    public String getName() {
        return name;
    }

    public String getCategory() {
        return category;
    }

    public String getThumbnailUrl() {
        return thumbnail_url;
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
        TriblerTorrent that = (TriblerTorrent) object;
        if (infohash == null) {
            return that.infohash == null;
        }
        return infohash.equals(that.infohash);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int hashCode() {
        return infohash.hashCode();
    }

}
