package org.tribler.android.restapi.json;

public class EventsStartEvent {

    public static final String TYPE = "events_start";

    private boolean tribler_started;
    private String version;

    EventsStartEvent() {
    }

    public boolean isTriblerStarted() {
        return tribler_started;
    }

    public String getVersion() {
        return version;
    }

}
