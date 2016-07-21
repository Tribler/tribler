package org.tribler.android;

import android.net.Uri;
import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Filter;
import android.widget.Filterable;
import android.widget.ImageView;
import android.widget.TextView;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Creates visual representation for channels and torrents in a list
 */
public class TriblerViewAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> implements Filterable {
    private static final int VIEW_TYPE_UNKNOWN = 0;
    private static final int VIEW_TYPE_CHANNEL = 1;
    private static final int VIEW_TYPE_TORRENT = 2;

    public interface OnClickListener {
        void onClick(TriblerChannel channel);

        void onClick(TriblerTorrent torrent);
    }

    public interface OnSwipeListener {
        void onSwipedRight(TriblerChannel channel);

        void onSwipedLeft(TriblerChannel channel);

        void onSwipedRight(TriblerTorrent torrent);

        void onSwipedLeft(TriblerTorrent torrent);
    }

    private List<Object> mDataList;
    private List<Object> mFilteredDataList;
    private TriblerViewAdapterFilter mFilter;
    private TriblerViewAdapterTouchCallback mTouchCallback;
    private OnClickListener mClickListener;
    private OnSwipeListener mSwipeListener;

    public TriblerViewAdapter() {
        mDataList = new ArrayList<>();
        mFilteredDataList = new ArrayList<>();
        mFilter = new TriblerViewAdapterFilter(this, mDataList);
        mTouchCallback = new TriblerViewAdapterTouchCallback(this);
    }

    /**
     * Attaches the Adapter to the provided RecyclerView. If Adapter is already
     * attached to a RecyclerView, it will first detach from the previous one. You can call this
     * method with {@code null} to detach it from the current RecyclerView.
     *
     * @param recyclerView The RecyclerView instance to which you want to add this helper or
     *                     {@code null} if you want to remove ItemTouchHelper from the current
     *                     RecyclerView.
     */
    public void attachToRecyclerView(@Nullable RecyclerView recyclerView) {
        if (recyclerView != null) {
            recyclerView.setAdapter(this);
        }
        mTouchCallback.attachToRecyclerView(recyclerView);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Filter getFilter() {
        return mFilter;
    }

    public OnClickListener getOnClickListener() {
        return mClickListener;
    }

    public void setOnClickListener(OnClickListener clickListener) {
        mClickListener = clickListener;
    }

    public OnSwipeListener getOnSwipeListener() {
        return mSwipeListener;
    }

    public void setOnSwipeListener(OnSwipeListener swipeListener) {
        mSwipeListener = swipeListener;
    }

    /**
     * @param adapterPosition The position in the adapter list
     * @return The item on the given adapter position
     */
    public Object getItem(int adapterPosition) {
        return mFilteredDataList.get(adapterPosition);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int getItemCount() {
        return mFilteredDataList.size();
    }

    /**
     * @param item The item to add to the adapter list
     * @return True if the item is successfully added, false otherwise
     */
    public boolean addItem(Object item) {
        int adapterPosition = mFilteredDataList.indexOf(item);
        if (adapterPosition < 0) {
            insertItem(getItemCount(), item);
        }
        return mDataList.add(item);
    }

    /**
     * @param item The item to remove from the adapter list
     * @return True if the item is successfully removed, false otherwise
     */
    public boolean removeItem(Object item) {
        int adapterPosition = mFilteredDataList.indexOf(item);
        if (adapterPosition >= 0) {
            removeItem(adapterPosition);
        }
        return mDataList.remove(item);
    }

    /**
     * Empty data list
     */
    public void clear() {
        mDataList.clear();
        mFilteredDataList.clear();
        notifyDataSetChanged();
    }

    public void setList(List<Object> list) {
        applyAndAnimateRemovals(list);
        applyAndAnimateAdditions(list);
        applyAndAnimateMovedItems(list);
    }

    private void applyAndAnimateRemovals(List<Object> list) {
        for (int i = mFilteredDataList.size() - 1; i >= 0; i--) {
            Object item = mFilteredDataList.get(i);
            if (!list.contains(item)) {
                removeItem(i);
            }
        }
    }

    private void applyAndAnimateAdditions(List<Object> list) {
        for (int i = 0, count = list.size(); i < count; i++) {
            Object item = list.get(i);
            if (!mFilteredDataList.contains(item)) {
                insertItem(i, item);
            }
        }
    }

    private void applyAndAnimateMovedItems(List<Object> list) {
        for (int toPosition = list.size() - 1; toPosition >= 0; toPosition--) {
            Object item = list.get(toPosition);
            int fromPosition = mFilteredDataList.indexOf(item);
            if (fromPosition >= 0 && fromPosition != toPosition) {
                moveItem(fromPosition, toPosition);
            }
        }
    }

    /**
     * @param adapterPosition The position of the item in adapter list to remove
     */
    private void removeItem(int adapterPosition) {
        mFilteredDataList.remove(adapterPosition);
        notifyItemRemoved(adapterPosition);
    }

    /**
     * @param adapterPosition The position in the adapter list of where to insert the item
     * @param item            The item to insert to the adapter list
     */
    private void insertItem(int adapterPosition, Object item) {
        mFilteredDataList.add(adapterPosition, item);
        notifyItemInserted(adapterPosition);
    }

    /**
     * @param fromPosition The position in the adapter list of the item to move from
     * @param toPosition   The position in the adapter list of the item to move to
     */
    private void moveItem(int fromPosition, int toPosition) {
        Object model = mFilteredDataList.remove(fromPosition);
        mFilteredDataList.add(toPosition, model);
        notifyItemMoved(fromPosition, toPosition);
    }

    /**
     * @param item The item to refresh the view of in the adapter list
     * @return True if the view of the item is successfully refreshed, false otherwise
     */
    public boolean itemChanged(Object item) {
        int adapterPosition = mFilteredDataList.indexOf(item);
        if (adapterPosition < 0) {
            return false;
        }
        notifyItemChanged(adapterPosition);
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int getItemViewType(int adapterPosition) {
        Object item = getItem(adapterPosition);
        if (item instanceof TriblerChannel) {
            return VIEW_TYPE_CHANNEL;
        } else if (item instanceof TriblerTorrent) {
            return VIEW_TYPE_TORRENT;
        }
        return VIEW_TYPE_UNKNOWN;
    }

    public class ChannelViewHolder extends RecyclerView.ViewHolder {
        public TextView name, votesCount, torrentsCount;
        public ImageView icon;

        public ChannelViewHolder(View itemView) {
            super(itemView);
            name = (TextView) itemView.findViewById(R.id.channel_name);
            votesCount = (TextView) itemView.findViewById(R.id.channel_votes_count);
            torrentsCount = (TextView) itemView.findViewById(R.id.channel_torrents_count);
            icon = (ImageView) itemView.findViewById(R.id.channel_icon);
        }
    }

    public class TorrentViewHolder extends RecyclerView.ViewHolder {
        public TextView name, seeders, size;
        public ImageView thumbnail;

        public TorrentViewHolder(View itemView) {
            super(itemView);
            name = (TextView) itemView.findViewById(R.id.torrent_name);
            seeders = (TextView) itemView.findViewById(R.id.torrent_seeders);
            size = (TextView) itemView.findViewById(R.id.torrent_size);
            thumbnail = (ImageView) itemView.findViewById(R.id.torrent_thumbnail);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        // Create new channel view
        if (viewType == VIEW_TYPE_CHANNEL) {
            View channelView = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.list_item_channel, parent, false);
            return new ChannelViewHolder(channelView);
        }
        // Create new torrent view
        else if (viewType == VIEW_TYPE_TORRENT) {
            View torrentView = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.list_item_torrent, parent, false);
            return new TorrentViewHolder(torrentView);
        }
        // Unknown view type
        else {
            return null;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onBindViewHolder(RecyclerView.ViewHolder viewHolder, int adapterPosition) {
        // Channel
        if (viewHolder instanceof ChannelViewHolder) {
            ChannelViewHolder holder = (ChannelViewHolder) viewHolder;
            final TriblerChannel channel = (TriblerChannel) getItem(adapterPosition);
            holder.name.setText(channel.getName());
            holder.votesCount.setText(String.valueOf(channel.getVotesCount()));
            holder.torrentsCount.setText(String.valueOf(channel.getTorrentsCount()));
            File icon = new File(channel.getIconUrl());
            if (icon.exists()) {
                holder.icon.setImageURI(Uri.fromFile(icon));
            }
            holder.itemView.setOnClickListener(new View.OnClickListener() {
                /**
                 * {@inheritDoc}
                 */
                @Override
                public void onClick(View view) {
                    if (mClickListener != null) {
                        mClickListener.onClick(channel);
                    }
                }
            });
        }
        // Torrent
        else if (viewHolder instanceof TorrentViewHolder) {
            TorrentViewHolder holder = (TorrentViewHolder) viewHolder;
            final TriblerTorrent torrent = (TriblerTorrent) getItem(adapterPosition);
            holder.name.setText(torrent.getName());
            holder.seeders.setText(String.valueOf(torrent.getNumSeeders()));
            holder.size.setText(String.valueOf(torrent.getSize()));
            File thumbnail = new File(torrent.getThumbnailUrl());
            if (thumbnail.exists()) {
                holder.thumbnail.setImageURI(Uri.fromFile(thumbnail));
            }
            holder.itemView.setOnClickListener(new View.OnClickListener() {
                /**
                 * {@inheritDoc}
                 */
                @Override
                public void onClick(View view) {
                    if (mClickListener != null) {
                        mClickListener.onClick(torrent);
                    }
                }
            });
        }
    }

}
