package org.tribler.android.restapi.json;

/**
 * Deserialization of JSON channels response
 */
public class ChannelsResponse {

    private TriblerChannel[] channels;

    public ChannelsResponse() {
    }

    public TriblerChannel[] getChannels() {
        return channels;
    }

}
