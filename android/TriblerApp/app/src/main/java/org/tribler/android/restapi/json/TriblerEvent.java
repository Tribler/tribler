package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON event
 */
public class TriblerEvent {

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
