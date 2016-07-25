package org.tribler.android.restapi.json;

import java.io.Serializable;

public class TriblerEvent implements Serializable {

    private String type;
    private Object event;

    public TriblerEvent() {
    }

    public String getType() {
        return type;
    }

    public Object getEvent() {
        return event;
    }

}
