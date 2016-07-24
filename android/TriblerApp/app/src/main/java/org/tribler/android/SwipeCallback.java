package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

public class SwipeCallback extends ItemTouchHelper.SimpleCallback {

    private final TriblerViewAdapter.OnSwipeListener _swipeListener;

    /**
     * Swipe left and right
     */
    public SwipeCallback(final TriblerViewAdapter.OnSwipeListener listener) {
        super(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT);
        _swipeListener = listener;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
        if (_swipeListener == null) {
            return;
        }
        // Swipe channel
        if (viewHolder instanceof TriblerViewAdapter.ChannelViewHolder) {
            TriblerChannel channel = ((TriblerViewAdapter.ChannelViewHolder) viewHolder).channel;
            if (swipeDir == ItemTouchHelper.LEFT) {
                _swipeListener.onSwipedLeft(channel);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                _swipeListener.onSwipedRight(channel);
            }
        }
        // Swipe torrent
        else if (viewHolder instanceof TriblerViewAdapter.TorrentViewHolder) {
            TriblerTorrent torrent = ((TriblerViewAdapter.TorrentViewHolder) viewHolder).torrent;
            if (swipeDir == ItemTouchHelper.LEFT) {
                _swipeListener.onSwipedLeft(torrent);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                _swipeListener.onSwipedRight(torrent);
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
