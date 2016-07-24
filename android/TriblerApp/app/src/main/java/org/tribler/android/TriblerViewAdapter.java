package org.tribler.android;

import android.net.Uri;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import org.tribler.android.ListFragment.IListFragmentInteractionListener;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.io.File;
import java.util.Collection;

import butterknife.BindView;
import butterknife.ButterKnife;

/**
 * {@link RecyclerView.Adapter} that can display a {@link TriblerChannel} and {@link TriblerTorrent}
 * and makes a call to the specified {@link IListFragmentInteractionListener}.
 */
public class TriblerViewAdapter extends FilterableRecyclerViewAdapter {
    private static final int VIEW_TYPE_UNKNOWN = 0;
    private static final int VIEW_TYPE_CHANNEL = 1;
    private static final int VIEW_TYPE_TORRENT = 2;

    private final OnClickListener mClickListener;
    private final ItemTouchHelper mTouchHelper;

    public TriblerViewAdapter(Collection<Object> objects, OnClickListener onClick, TriblerViewAdapter.OnSwipeListener onSwipe) {
        super(objects);
        mClickListener = onClick;
        mTouchHelper = new ItemTouchHelper(new SwipeCallback(onSwipe));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttachedToRecyclerView(RecyclerView recyclerView) {
        mTouchHelper.attachToRecyclerView(recyclerView);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetachedFromRecyclerView(RecyclerView recyclerView) {
        mTouchHelper.attachToRecyclerView(null);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int getItemViewType(int adapterPosition) {
        Object item = getObject(adapterPosition);
        if (item instanceof TriblerChannel) {
            return VIEW_TYPE_CHANNEL;
        } else if (item instanceof TriblerTorrent) {
            return VIEW_TYPE_TORRENT;
        }
        return VIEW_TYPE_UNKNOWN;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        // Create new channel view
        if (viewType == VIEW_TYPE_CHANNEL) {
            View channelView = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.fragment_list_item_channel, parent, false);
            return new ChannelViewHolder(channelView);
        }
        // Create new torrent view
        else if (viewType == VIEW_TYPE_TORRENT) {
            View torrentView = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.fragment_list_item_torrent, parent, false);
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
    public void onBindViewHolder(final RecyclerView.ViewHolder viewHolder, int adapterPosition) {
        // Channel
        if (viewHolder instanceof ChannelViewHolder) {
            ChannelViewHolder holder = (ChannelViewHolder) viewHolder;

            holder.channel = (TriblerChannel) getObject(adapterPosition);
            holder.name.setText(holder.channel.getName());
            holder.votesCount.setText(String.valueOf(holder.channel.getVotesCount()));
            holder.torrentsCount.setText(String.valueOf(holder.channel.getTorrentsCount()));
            File icon = new File(holder.channel.getIconUrl());
            if (icon.exists()) {
                holder.icon.setImageURI(Uri.fromFile(icon));
            }
            holder.view.setOnClickListener(view -> {
                if (null != mClickListener) {
                    // Notify the active callbacks interface (the activity, if the
                    // fragment is attached to one) that an item has been selected.
                    mClickListener.onClick(holder.channel);
                }
            });
        }
        // Torrent
        else if (viewHolder instanceof TorrentViewHolder) {
            TorrentViewHolder holder = (TorrentViewHolder) viewHolder;

            holder.torrent = (TriblerTorrent) getObject(adapterPosition);
            holder.name.setText(holder.torrent.getName());
            holder.seedersCount.setText(String.valueOf(holder.torrent.getNumSeeders()));
            holder.size.setText(String.valueOf(holder.torrent.getSize()));
            File thumbnail = new File(holder.torrent.getThumbnailUrl());
            if (thumbnail.exists()) {
                holder.thumbnail.setImageURI(Uri.fromFile(thumbnail));
            }
            holder.view.setOnClickListener(view -> {
                if (null != mClickListener) {
                    // Notify the active callbacks interface (the activity, if the
                    // fragment is attached to one) that an item has been selected.
                    mClickListener.onClick(holder.torrent);
                }
            });
        }
    }

    public class ChannelViewHolder extends RecyclerView.ViewHolder {

        public TriblerChannel channel;

        public final View view;

        @BindView(R.id.channel_name)
        TextView name;
        @BindView(R.id.channel_votes_count)
        TextView votesCount;
        @BindView(R.id.channel_torrents_count)
        TextView torrentsCount;
        @BindView(R.id.channel_icon)
        ImageView icon;

        public ChannelViewHolder(View view) {
            super(view);
            ButterKnife.bind(this, view);
            this.view = view;
        }
    }

    public class TorrentViewHolder extends RecyclerView.ViewHolder {

        public TriblerTorrent torrent;

        public final View view;

        @BindView(R.id.torrent_name)
        TextView name;
        @BindView(R.id.torrent_seeders_count)
        TextView seedersCount;
        @BindView(R.id.torrent_size)
        TextView size;
        @BindView(R.id.torrent_thumbnail)
        ImageView thumbnail;

        public TorrentViewHolder(View view) {
            super(view);
            ButterKnife.bind(this, view);
            this.view = view;
        }
    }

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
}
