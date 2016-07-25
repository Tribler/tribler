package org.tribler.android.restapi.json;

import java.io.Serializable;

public class SearchResultTorrentEvent implements Serializable {

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
