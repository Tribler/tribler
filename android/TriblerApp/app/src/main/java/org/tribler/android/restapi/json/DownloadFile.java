package org.tribler.android.restapi.json;

public class DownloadFile {

    private int index;
    private String name;
    private long size;
    private boolean included;

    DownloadFile() {
    }

    public int getIndex() {
        return index;
    }

    public String getName() {
        return name;
    }

    public long getSize() {
        return size;
    }

    public boolean isIncluded() {
        return included;
    }

}
