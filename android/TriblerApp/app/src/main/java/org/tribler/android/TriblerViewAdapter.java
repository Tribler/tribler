package org.tribler.android;

import android.net.Uri;
import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import java.util.List;

/**
 * Creates visual representation for channels and torrents in a list
 */
public class TriblerViewAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {
    private static final int VIEW_TYPE_UNKNOWN = 0;
    private static final int VIEW_TYPE_CHANNEL = 1;
    private static final int VIEW_TYPE_TORRENT = 2;

    private List<Object> mList;

    public TriblerViewAdapter(List<Object> list) {
        mList = list;
    }

    /**
     * @param list The new data set to replace the current one
     */
    public void setList(List<Object> list) {
        mList = list;
    }

    /**
     * @return The list being displayed
     */
    public List<Object> getList() {
        return mList;
    }

    /**
     * @param adapterPosition The position in the adapter list
     * @return The item on the given adapter position
     */
    public Object getItem(int adapterPosition) {
        return mList.get(adapterPosition);
    }

    /**
     * @return The amount of items in the data set (invoked by the layout manager)
     */
    @Override
    public int getItemCount() {
        return mList.size();
    }

    /**
     * @param adapterPosition The position in the adapter list
     * @return VIEW_TYPE_CHANNEL | VIEW_TYPE_TORRENT | VIEW_TYPE_UNKNOWN based on class type
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
        public TextView name, torrentsCount, commentsCount;
        public ImageView icon;

        public ChannelViewHolder(View itemView) {
            super(itemView);
            name = (TextView) itemView.findViewById(R.id.channel_name);
            torrentsCount = (TextView) itemView.findViewById(R.id.channel_videos_count);
            commentsCount = (TextView) itemView.findViewById(R.id.channel_comments_count);
            icon = (ImageView) itemView.findViewById(R.id.channel_icon);
        }
    }

    public class TorrentViewHolder extends RecyclerView.ViewHolder {
        public TextView title, duration, bitrate;
        public ImageView thumbnail;

        public TorrentViewHolder(View itemView) {
            super(itemView);
            title = (TextView) itemView.findViewById(R.id.torrent_title);
            duration = (TextView) itemView.findViewById(R.id.torrent_duration);
            bitrate = (TextView) itemView.findViewById(R.id.torrent_bitrate);
            thumbnail = (ImageView) itemView.findViewById(R.id.torrent_thumbnail);
        }
    }

    /**
     * @param parent   The group to which the view should be added
     * @param viewType The type of view to create
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
     * Replaces the contents of a view (invoked by the layout manager)
     *
     * @param holder   The holder of the view of an item
     * @param position The position of the item in the data set
     */
    @Override
    public void onBindViewHolder(RecyclerView.ViewHolder holder, int position) {
        // Channel
        if (holder instanceof ChannelViewHolder) {
            ChannelViewHolder view = (ChannelViewHolder) holder;
            TriblerChannel channel = (TriblerChannel) getItem(position);
            view.name.setText(channel.getName());
            view.torrentsCount.setText(String.valueOf(channel.getTorrentsCount()));
            view.commentsCount.setText(String.valueOf(channel.getCommentsCount()));
            view.icon.setImageURI(Uri.parse(channel.getIconUrl()));
        }
        // Torrent
        else if (holder instanceof TorrentViewHolder) {
            TorrentViewHolder view = (TorrentViewHolder) holder;
            TriblerTorrent torrent = (TriblerTorrent) getItem(position);
            view.title.setText(torrent.getTitle());
            view.duration.setText(String.valueOf(torrent.getDuration()));
            view.bitrate.setText(String.valueOf(torrent.getBitrate()));
            view.thumbnail.setImageURI(Uri.parse(torrent.getThumbnailUrl()));
        }
    }

}