package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

public class SwipeCallback extends ItemTouchHelper.SimpleCallback {

    private final TriblerViewAdapter.OnSwipeListener mListener;

    /**
     * Swipe left and right
     */
    public SwipeCallback(final TriblerViewAdapter.OnSwipeListener listener) {
        super(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT);
        mListener = listener;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
        if (mListener == null) {
            return;
        }
        // Swipe channel
        if (viewHolder instanceof TriblerViewAdapter.ChannelViewHolder) {
            TriblerChannel channel = ((TriblerViewAdapter.ChannelViewHolder) viewHolder).channel;
            if (swipeDir == ItemTouchHelper.LEFT) {
                mListener.onSwipedLeft(channel);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                mListener.onSwipedRight(channel);
            }
        }
        // Swipe torrent
        else if (viewHolder instanceof TriblerViewAdapter.TorrentViewHolder) {
            TriblerTorrent torrent = ((TriblerViewAdapter.TorrentViewHolder) viewHolder).torrent;
            if (swipeDir == ItemTouchHelper.LEFT) {
                mListener.onSwipedLeft(torrent);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                mListener.onSwipedRight(torrent);
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
}
