package org.tribler.android.restapi.json;

import java.util.List;

public class DownloadsResponse {

    private List<TriblerDownload> downloads;

    DownloadsResponse() {
    }

    public List<TriblerDownload> getDownloads() {
        return downloads;
    }

}
