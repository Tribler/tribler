package org.tribler.android;

import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

public class SwipeCallback extends ItemTouchHelper.SimpleCallback {

    protected TriblerViewAdapter.OnSwipeListener swipeListener;

    /**
     * Swipe left and right
     */
    public SwipeCallback() {
        super(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT);
    }

    @Nullable
    public TriblerViewAdapter.OnSwipeListener getSwipeListener() {
        return swipeListener;
    }

    public void setSwipeListener(@Nullable TriblerViewAdapter.OnSwipeListener listener) {
        swipeListener = listener;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
        if (swipeListener == null) {
            return;
        }
        // Swipe channel
        if (viewHolder instanceof TriblerViewAdapter.ChannelViewHolder) {
            TriblerChannel channel = ((TriblerViewAdapter.ChannelViewHolder) viewHolder).channel;
            if (swipeDir == ItemTouchHelper.LEFT) {
                swipeListener.onSwipedLeft(channel);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                swipeListener.onSwipedRight(channel);
            }
        }
        // Swipe torrent
        else if (viewHolder instanceof TriblerViewAdapter.TorrentViewHolder) {
            TriblerTorrent torrent = ((TriblerViewAdapter.TorrentViewHolder) viewHolder).torrent;
            if (swipeDir == ItemTouchHelper.LEFT) {
                swipeListener.onSwipedLeft(torrent);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                swipeListener.onSwipedRight(torrent);
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
