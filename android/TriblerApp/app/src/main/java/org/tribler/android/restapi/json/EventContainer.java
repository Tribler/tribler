package org.tribler.android.restapi.json;

import com.google.gson.JsonElement;

public class EventContainer {

    private String type;
    private JsonElement event;

    EventContainer() {
    }

    public String getType() {
        return type;
    }

    public JsonElement getEvent() {
        return event;
    }

}
