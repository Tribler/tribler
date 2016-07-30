package org.tribler.android.restapi.json;

import java.io.Serializable;

public class ShutdownAck implements Serializable {

    private boolean shutdown;
    private float gracetime;

    public ShutdownAck() {
    }

    public boolean getShutdown() {
        return shutdown;
    }

    public float getGracetime() {
        return gracetime;
    }

}
