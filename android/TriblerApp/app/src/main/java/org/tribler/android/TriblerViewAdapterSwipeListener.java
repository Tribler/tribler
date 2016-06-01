package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

public class TriblerViewAdapterSwipeListener extends ItemTouchHelper.SimpleCallback {

    private ItemTouchHelper mHelper;
    private TriblerViewAdapter mAdapter;

    /**
     * Swipe left and right
     */
    public TriblerViewAdapterSwipeListener(TriblerViewAdapter adapter) {
        super(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT);
        mHelper = new ItemTouchHelper(this);
        mAdapter = adapter;
    }

    public void attachToRecyclerView(RecyclerView view) {
        mHelper.attachToRecyclerView(view);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
        TriblerViewAdapter.OnSwipeListener listener = mAdapter.getOnSwipeListener();
        if (listener == null)
            return;

        int adapterPosition = viewHolder.getAdapterPosition();
        // Swipe channel
        if (viewHolder instanceof TriblerViewAdapter.ChannelViewHolder) {
            TriblerChannel channel = (TriblerChannel) mAdapter.getItem(adapterPosition);
            if (swipeDir == ItemTouchHelper.LEFT) {
                listener.onSwipedLeft(viewHolder.itemView, channel);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                listener.onSwipedRight(viewHolder.itemView, channel);
            }
        }
        // Swipe torrent
        else if (viewHolder instanceof TriblerViewAdapter.TorrentViewHolder) {
            TriblerTorrent torrent = (TriblerTorrent) mAdapter.getItem(adapterPosition);
            if (swipeDir == ItemTouchHelper.LEFT) {
                listener.onSwipedLeft(viewHolder.itemView, torrent);
            } else if (swipeDir == ItemTouchHelper.RIGHT) {
                listener.onSwipedRight(viewHolder.itemView, torrent);
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
