package org.tribler.android.restapi.json;

public class ChannelDiscoveredEvent {

    public static final String TYPE = "channel_discovered";

    private String name, description, dispersy_cid;

    ChannelDiscoveredEvent() {
    }

    public String getName() {
        return name;
    }

    public String getDescription() {
        return description;
    }

    public String getDispersyCid() {
        return dispersy_cid;
    }

}
