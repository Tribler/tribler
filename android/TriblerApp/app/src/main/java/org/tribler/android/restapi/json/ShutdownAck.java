package org.tribler.android.restapi.json;

public class ShutdownAck {

    private boolean shutdown;
    private float gracetime;

    ShutdownAck() {
    }

    public boolean getShutdown() {
        return shutdown;
    }

    public float getGracetime() {
        return gracetime;
    }

}
