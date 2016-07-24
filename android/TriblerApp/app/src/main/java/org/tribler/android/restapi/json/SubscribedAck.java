package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON channel subscribe acknowledgement
 */
public class SubscribedAck {

    private boolean subscribed;

    public SubscribedAck() {
    }

    public boolean getSubscribed() {
        return subscribed;
    }

}
