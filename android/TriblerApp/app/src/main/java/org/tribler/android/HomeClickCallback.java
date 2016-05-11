package org.tribler.android;

import android.view.View;

public class HomeClickCallback implements TriblerViewClickListener.OnItemClickListener {

    private TriblerViewAdapter mAdapter;

    public HomeClickCallback(TriblerViewAdapter adapter) {
        mAdapter = adapter;
    }

    @Override
    public void onItemClick(View view, int adapterPosition) {
        Object item = mAdapter.getItem(adapterPosition);
        if (item instanceof TriblerChannel) {
            //TODO: open channel
        } else if (item instanceof TriblerTorrent) {
            //TODO: play video
        }
    }
}
