package org.tribler.android.restapi.json;

public class SubscribedChannelsResponse {

    private TriblerChannel[] subscribed;

    SubscribedChannelsResponse() {
    }

    public TriblerChannel[] getSubscribed() {
        return subscribed;
    }

}
