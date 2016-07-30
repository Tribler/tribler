package org.tribler.android.restapi.json;

public class TriblerTorrent {

    private int id, num_seeders, num_leechers, last_tracker_check;
    long size;
    private String infohash, name, category, thumbnail_url;

    public TriblerTorrent() {
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
        if (thumbnail_url == null) {
            thumbnail_url = ""; //TODO: default image
        }
        return thumbnail_url;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        TriblerTorrent that = (TriblerTorrent) o;

        if (id != that.id) return false;
        if (num_seeders != that.num_seeders) return false;
        if (num_leechers != that.num_leechers) return false;
        if (last_tracker_check != that.last_tracker_check) return false;
        if (size != that.size) return false;
        if (!infohash.equals(that.infohash)) return false;
        if (name != null ? !name.equals(that.name) : that.name != null) return false;
        if (category != null ? !category.equals(that.category) : that.category != null)
            return false;
        return thumbnail_url != null ? thumbnail_url.equals(that.thumbnail_url) : that.thumbnail_url == null;

    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int hashCode() {
        return infohash.hashCode();
    }
}
