package org.tribler.android.restapi.json;

public class SearchResultChannelEvent {

    public static final String TYPE = "search_result_channel";

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
