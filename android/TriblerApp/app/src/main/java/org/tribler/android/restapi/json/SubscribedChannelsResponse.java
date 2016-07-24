package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON subscribed channels response
 */
public class SubscribedChannelsResponse {

    private TriblerChannel[] subscribed;

    public SubscribedChannelsResponse() {
    }

    public TriblerChannel[] getSubscribed() {
        return subscribed;
    }

}
