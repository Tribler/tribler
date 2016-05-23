package org.tribler.android;

import android.view.View;

public class HomeClickListener implements TriblerViewClickListener.OnItemClickListener {

    private TriblerViewAdapter mAdapter;

    public HomeClickListener(TriblerViewAdapter adapter) {
        mAdapter = adapter;
    }

    /**
     * {@inheritDoc}
     */
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
