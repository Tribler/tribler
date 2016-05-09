package org.tribler.android;

import android.widget.SearchView;

public class MySearchListener implements SearchView.OnQueryTextListener {

    @Override
    public boolean onQueryTextSubmit(String s) {
        return false;
    }

    @Override
    public boolean onQueryTextChange(String s) {
        return false;
    }
}
