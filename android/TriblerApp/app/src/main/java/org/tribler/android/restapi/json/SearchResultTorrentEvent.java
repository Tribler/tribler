package org.tribler.android.restapi.json;

public class SearchResultTorrentEvent {

    public static final String TYPE = "search_result_torrent";

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
