package org.tribler.android;

/**
 * Deserialization of JSON search result torrent event
 */
public class SearchResultTorrentEvent {

    private String query;
    private TriblerTorrent result;

    public SearchResultTorrentEvent() {
    }

    public String getQuery() {
        return query;
    }

    public TriblerTorrent getResult() {
        return result;
    }

}
