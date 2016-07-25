package org.tribler.android.restapi.json;

import java.io.Serializable;

public class ChannelsResponse implements Serializable {

    private TriblerChannel[] channels;

    public ChannelsResponse() {
    }

    public TriblerChannel[] getChannels() {
        return channels;
    }

}
