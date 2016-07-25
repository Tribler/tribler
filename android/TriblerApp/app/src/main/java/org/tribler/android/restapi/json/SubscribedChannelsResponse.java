package org.tribler.android.restapi.json;

import java.io.Serializable;

public class SubscribedChannelsResponse implements Serializable {

    private TriblerChannel[] subscribed;

    public SubscribedChannelsResponse() {
    }

    public TriblerChannel[] getSubscribed() {
        return subscribed;
    }

}
