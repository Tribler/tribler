package org.tribler.android.restapi.json;

import java.io.Serializable;

public class SearchResultChannelEvent implements Serializable {

    private String query;
    private TriblerChannel result;

    public SearchResultChannelEvent() {
    }

    public String getQuery() {
        return query;
    }

    public TriblerChannel getResult() {
        return result;
    }

}
