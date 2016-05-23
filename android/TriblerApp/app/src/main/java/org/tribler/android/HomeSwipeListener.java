package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

public class HomeSwipeListener extends ItemTouchHelper.SimpleCallback {

    private TriblerViewAdapter mAdapter;

    public HomeSwipeListener(TriblerViewAdapter adapter) {
        super(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT);
        mAdapter = adapter;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
        int adapterPosition = viewHolder.getAdapterPosition();
        // Swipe channel
        if (viewHolder instanceof TriblerViewAdapter.ChannelViewHolder) {
            TriblerChannel channel = (TriblerChannel) mAdapter.getItem(adapterPosition);
            if (swipeDir == ItemTouchHelper.LEFT) {
                //TODO: un-subscribe / not interested
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                //TODO: subscribe / favorite
            }
        }
        // Swipe torrent
        else if (viewHolder instanceof TriblerViewAdapter.TorrentViewHolder) {
            TriblerTorrent torrent = (TriblerTorrent) mAdapter.getItem(adapterPosition);
            if (swipeDir == ItemTouchHelper.LEFT) {
                //TODO: not interested
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                //TODO: watch later
            }
        }
    }

    /**
     * Not draggable
     */
    @Override
    public boolean isLongPressDragEnabled() {
        return false;
    }

    /**
     * Not draggable
     */
    @Override
    public boolean onMove(RecyclerView recyclerView, RecyclerView.ViewHolder viewHolder,
                          RecyclerView.ViewHolder target) {
        return false;
    }
};
