package org.tribler.android.restapi.json;

import java.io.Serializable;

public class SubscribedAck implements Serializable {

    private boolean subscribed;

    public SubscribedAck() {
    }

    public boolean getSubscribed() {
        return subscribed;
    }

}
