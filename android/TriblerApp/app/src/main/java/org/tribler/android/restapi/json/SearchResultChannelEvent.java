package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON search result channel event
 */
public class SearchResultChannelEvent {

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
