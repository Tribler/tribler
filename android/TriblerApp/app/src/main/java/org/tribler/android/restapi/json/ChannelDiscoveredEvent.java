package org.tribler.android.restapi.json;

public class ChannelDiscoveredEvent {

    public static final String TYPE = "channel_discovered";

    private String name;
    private String dispersy_cid;
    private String description;

    ChannelDiscoveredEvent() {
    }

    public String getName() {
        return name;
    }

    public String getDispersyCid() {
        return dispersy_cid;
    }

    public String getDescription() {
        return description;
    }
}
