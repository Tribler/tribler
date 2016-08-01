package org.tribler.android.restapi.json;

public class ShutdownAck {

    private boolean shutdown;
    private float gracetime;

    ShutdownAck() {
    }

    public boolean isShutdown() {
        return shutdown;
    }

    public float getGracetime() {
        return gracetime;
    }

}
