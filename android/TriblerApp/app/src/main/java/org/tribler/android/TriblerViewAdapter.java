package org.tribler.android;

import android.net.Uri;
import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Filter;
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
    public static final int VIEW_TYPE_UNKNOWN = 0;
    public static final int VIEW_TYPE_CHANNEL = 1;
    public static final int VIEW_TYPE_TORRENT = 2;

    private OnClickListener _clickListener;
    private final SwipeCallback _swipeCallback;
    private final ItemTouchHelper _touchHelper;
    private final TriblerViewAdapterFilter _filter;

    public TriblerViewAdapter(Collection<Object> objects) {
        super(objects);
        _swipeCallback = new SwipeCallback();
        _touchHelper = new ItemTouchHelper(_swipeCallback);
        _filter = new TriblerViewAdapterFilter(this);
    }

    @Nullable
    public OnClickListener getClickListener() {
        return _clickListener;
    }

    @Nullable
    public OnSwipeListener getSwipeListener() {
        return _swipeCallback.getSwipeListener();
    }

    /**
     * @param listener OnClickListener that will listen to the view items being clicked
     */
    public void setClickListener(@Nullable OnClickListener listener) {
        _clickListener = listener;
    }

    /**
     * @param listener OnSwipeListener that will listen to the view items being swiped
     */
    public void setSwipeListener(@Nullable OnSwipeListener listener) {
        _swipeCallback.setSwipeListener(listener);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Filter getFilter() {
        return _filter;
    }

    @Nullable
    public TriblerChannel findByDispersyCid(String dispersyCid) {
        for (Object object : getData()) {
            if (object instanceof TriblerChannel) {
                TriblerChannel channel = (TriblerChannel) object;
                if (dispersyCid.equals(channel.getDispersyCid())) {
                    return channel;
                }
            }
        }
        return null;
    }

    @Nullable
    public TriblerTorrent findByInfohash(String infohash) {
        for (Object object : getData()) {
            if (object instanceof TriblerTorrent) {
                TriblerTorrent torrent = (TriblerTorrent) object;
                if (infohash.equals(torrent.getInfohash())) {
                    return torrent;
                }
            }
        }
        return null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttachedToRecyclerView(RecyclerView recyclerView) {
        _touchHelper.attachToRecyclerView(recyclerView);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetachedFromRecyclerView(RecyclerView recyclerView) {
        _touchHelper.attachToRecyclerView(null);
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
            Log.e("onCreateViewHolder", String.format("Unknown view type: %d", viewType));
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
            if (holder.channel.isSubscribed()) {
                holder.votesIcon.setImageResource(R.drawable.ic_list_star);
            } else {
                holder.votesIcon.setImageResource(R.drawable.ic_list_star_outline);
            }
            // Set src in xml only api 21+
            holder.torrentsIcon.setImageResource(R.drawable.ic_list_play);
            holder.torrentsCount.setText(String.valueOf(holder.channel.getTorrentsCount()));
            String url = holder.channel.getIconUrl();
            File icon;
            if (url != null && (icon = new File(url)).exists()) {
                holder.icon.setImageURI(Uri.fromFile(icon));
            } else {
                holder.nameCapital.setText(MyUtils.getCapitals(holder.channel.getName(), 2));
                MyUtils.setCicleBackground(holder.icon, MyUtils.getColor(holder.channel.hashCode()));
            }
            holder.view.setOnClickListener(view -> {
                if (_clickListener != null) {
                    // Notify the active callbacks interface (the activity, if the
                    // fragment is attached to one) that an item has been selected.
                    _clickListener.onClick(holder.channel);
                }
            });
        }
        // Torrent
        else if (viewHolder instanceof TorrentViewHolder) {
            TorrentViewHolder holder = (TorrentViewHolder) viewHolder;

            holder.torrent = (TriblerTorrent) getObject(adapterPosition);
            holder.name.setText(holder.torrent.getName());
            holder.size.setText(MyUtils.humanReadableByteCount(holder.torrent.getSize(), true));
            String category = holder.torrent.getCategory();
            holder.category.setText(category);
            String url = holder.torrent.getThumbnailUrl();
            File thumbnail;
            if (url != null && (thumbnail = new File(url)).exists()) {
                holder.thumbnail.setImageURI(Uri.fromFile(thumbnail));
            } else {
                if (category == null) {
                    category = "";
                }
                switch (category) {
                    case "Video":
                        holder.thumbnail.setBackgroundResource(R.drawable.ic_list_movie);
                        break;

                    case "Audio":
                        holder.thumbnail.setBackgroundResource(R.drawable.ic_list_music_note);
                        break;

                    case "Document":
                        holder.thumbnail.setBackgroundResource(R.drawable.ic_list_document);
                        break;

                    case "Compressed":
                        holder.thumbnail.setBackgroundResource(R.drawable.ic_list_compressed);
                        break;

                    case "xxx":
                        holder.thumbnail.setBackgroundResource(R.drawable.ic_list_xxx);
                        break;

                    case "other":
                        holder.thumbnail.setBackgroundResource(R.drawable.ic_list_minus);
                        break;
                }
            }
            holder.view.setOnClickListener(view -> {
                if (_clickListener != null) {
                    // Notify the active callbacks interface (the activity, if the
                    // fragment is attached to one) that an item has been selected.
                    _clickListener.onClick(holder.torrent);
                }
            });
        }
    }

    public class ChannelViewHolder extends RecyclerView.ViewHolder {

        public TriblerChannel channel;

        public final View view;

        @BindView(R.id.channel_icon)
        ImageView icon;
        @BindView(R.id.channel_capital)
        TextView nameCapital;
        @BindView(R.id.channel_name)
        TextView name;
        @BindView(R.id.channel_torrents_icon)
        ImageView torrentsIcon;
        @BindView(R.id.channel_torrents_count)
        TextView torrentsCount;
        @BindView(R.id.channel_votes_icon)
        ImageView votesIcon;
        @BindView(R.id.channel_votes_count)
        TextView votesCount;

        public ChannelViewHolder(View view) {
            super(view);
            ButterKnife.bind(this, view);
            this.view = view;
        }
    }

    public class TorrentViewHolder extends RecyclerView.ViewHolder {

        public TriblerTorrent torrent;

        public final View view;

        @BindView(R.id.torrent_thumbnail)
        ImageView thumbnail;
        @BindView(R.id.torrent_name)
        TextView name;
        @BindView(R.id.torrent_size)
        TextView size;
        @BindView(R.id.torrent_category)
        TextView category;

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
