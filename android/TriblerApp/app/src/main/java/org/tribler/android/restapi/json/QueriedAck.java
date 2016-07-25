package org.tribler.android.restapi.json;

import java.io.Serializable;

public class QueriedAck implements Serializable {

    private boolean queried;

    public QueriedAck() {
    }

    public boolean getQueried() {
        return queried;
    }

}
