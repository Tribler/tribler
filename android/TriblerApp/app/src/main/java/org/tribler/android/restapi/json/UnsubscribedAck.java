package org.tribler.android.restapi.json;

import java.io.Serializable;

public class UnsubscribedAck implements Serializable {

    private boolean unsubscribed;

    public UnsubscribedAck() {
    }

    public boolean getUnsubscribed() {
        return unsubscribed;
    }

}
