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
    private TriblerViewAdapterFilter mFilter;
    private TriblerViewAdapterTouchCallback mTouchCallback;
    private OnClickListener mClickListener;
    private OnSwipeListener mSwipeListener;

    public TriblerViewAdapter() {
        mDataList = new ArrayList<>();
        mFilter = new TriblerViewAdapterFilter(this, mDataList);
        mTouchCallback = new TriblerViewAdapterTouchCallback(this);
    }

    public void attachToRecyclerView(@Nullable RecyclerView view) {
        if (view != null) {
            view.setAdapter(this);
        }
        mTouchCallback.attachToRecyclerView(view);
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
     * Empty data list
     */
    public void clear() {
        mDataList.clear();
        notifyDataSetChanged();
    }

    /**
     * @param item The item to add to the adapter list
     * @return True if the item is successfully added, false otherwise
     */
    public boolean addItem(Object item) {
        int adapterPosition = getItemCount();
        boolean inserted = mDataList.add(item);
        if (inserted) {
            notifyItemInserted(adapterPosition);
        }
        return inserted;
    }

    /**
     * @param item The item to remove from the adapter list
     * @return True if the item is successfully removed, false otherwise
     */
    public boolean removeItem(Object item) {
        int adapterPosition = mDataList.indexOf(item);
        if (adapterPosition < 0) {
            return false;
        }
        mDataList.remove(adapterPosition);
        notifyItemRemoved(adapterPosition);
        return true;
    }

    /**
     * @param item The item to refresh the view of in the adapter list
     * @return True if the view of the item is successfully refreshed, false otherwise
     */
    public boolean updateItem(Object item) {
        int adapterPosition = mDataList.indexOf(item);
        if (adapterPosition < 0) {
            return false;
        }
        notifyItemChanged(adapterPosition);
        return true;
    }

    /**
     * @param adapterPosition The position in the adapter list
     * @return The item on the given adapter position
     */
    public Object getItem(int adapterPosition) {
        return mDataList.get(adapterPosition);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int getItemCount() {
        return mDataList.size();
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
        public TextView name, torrentsCount, votesCount;
        public ImageView icon;

        public ChannelViewHolder(View itemView) {
            super(itemView);
            name = (TextView) itemView.findViewById(R.id.channel_name);
            torrentsCount = (TextView) itemView.findViewById(R.id.channel_torrents_count);
            votesCount = (TextView) itemView.findViewById(R.id.channel_votes_count);
            icon = (ImageView) itemView.findViewById(R.id.channel_icon);
        }
    }

    public class TorrentViewHolder extends RecyclerView.ViewHolder {
        public TextView name, duration, bitrate;
        public ImageView thumbnail;

        public TorrentViewHolder(View itemView) {
            super(itemView);
            name = (TextView) itemView.findViewById(R.id.torrent_name);
            duration = (TextView) itemView.findViewById(R.id.torrent_duration);
            bitrate = (TextView) itemView.findViewById(R.id.torrent_bitrate);
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
            holder.torrentsCount.setText(String.valueOf(channel.getTorrentsCount()));
            holder.votesCount.setText(String.valueOf(channel.getVotesCount()));
            holder.icon.setImageURI(Uri.parse(channel.getIconUrl()));
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
            holder.duration.setText(String.valueOf(torrent.getDuration()));
            holder.bitrate.setText(String.valueOf(torrent.getBitrate()));
            holder.thumbnail.setImageURI(Uri.parse(torrent.getThumbnailUrl()));
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
