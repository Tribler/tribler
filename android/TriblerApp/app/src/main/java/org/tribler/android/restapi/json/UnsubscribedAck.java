package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON channel un-subscribe acknowledgement
 */
public class UnsubscribedAck {

    private boolean unsubscribed;

    public UnsubscribedAck() {
    }

    public boolean getUnsubscribed() {
        return unsubscribed;
    }

}
