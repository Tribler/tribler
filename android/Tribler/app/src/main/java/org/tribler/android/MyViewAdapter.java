package org.tribler.android;

import android.net.Uri;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import java.util.List;

/**
 * Creates visual representation for channels and torrents in a list
 */
public class MyViewAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {

    private static final int VIEW_TYPE_CHANNEL = 1;
    private static final int VIEW_TYPE_TORRENT = 2;

    private List<Object> mData;

    public MyViewAdapter(List<Object> mData) {
        this.mData = mData;
    }

    @Override
    /**
     * @return The amount of items in the data set (invoked by the layout manager)
     */
    public int getItemCount() {
        return mData.size();
    }

    @Override
    /**
     * @return VIEW_TYPE_CHANNEL | VIEW_TYPE_TORRENT based on class type
     */
    public int getItemViewType(int position) {
        if (mData.get(position) instanceof TriblerChannel) {
            return VIEW_TYPE_CHANNEL;
        }
        return VIEW_TYPE_TORRENT;
    }

    public class ChannelViewHolder extends RecyclerView.ViewHolder {
        public TextView name, videosCount, commentsCount;
        public ImageView icon;

        public ChannelViewHolder(View itemView) {
            super(itemView);
            name = (TextView) itemView.findViewById(R.id.channel_name);
            videosCount = (TextView) itemView.findViewById(R.id.channel_videos_count);
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

    @Override
    /**
     * @param parent    The group to which the view should be added
     * @param viewType  The
     */
    public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        if (viewType == VIEW_TYPE_CHANNEL) {
            // Create new channel view
            View channelView = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.list_item_channel, parent, false);
            return new ChannelViewHolder(channelView);
        }
        // Create new torrent view
        View torrentView = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.list_item_torrent, parent, false);
        return new TorrentViewHolder(torrentView);
    }

    @Override
    /**
     * Replaces the contents of a view (invoked by the layout manager)
     * @param holder    The holder of the view of an item
     * @param position  The position of the item in the data set
     */
    public void onBindViewHolder(RecyclerView.ViewHolder holder, int position) {
        if (holder instanceof ChannelViewHolder) {
            ChannelViewHolder view = (ChannelViewHolder) holder;
            TriblerChannel channel = (TriblerChannel) mData.get(position);
            view.name.setText(channel.getName());
            view.videosCount.setText(channel.getVideosCount());
            view.commentsCount.setText(channel.getCommentsCount());
            view.icon.setImageURI(Uri.parse(channel.getIconUrl()));
        } else {
            TorrentViewHolder view = (TorrentViewHolder) holder;
            TriblerTorrent torrent = (TriblerTorrent) mData.get(position);
            view.title.setText(torrent.getTitle());
            view.duration.setText(torrent.getDuration());
            view.bitrate.setText(torrent.getBitrate());
            view.thumbnail.setImageURI(Uri.parse(torrent.getThumbnailUrl()));
        }
    }

    ItemTouchHelper.SimpleCallback mItemTouchCallback =
            new ItemTouchHelper.SimpleCallback(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT) {

                @Override
                public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
                    if (swipeDir == ItemTouchHelper.LEFT) {
                        //Remove swiped item from list and notify the RecyclerView
                    } else {
                        //Do something else
                    }
                }

                @Override
                /**
                 * Not draggable
                 */
                public boolean onMove(RecyclerView recyclerView, RecyclerView.ViewHolder viewHolder, RecyclerView.ViewHolder target) {
                    return false;
                }
            };

    ItemTouchHelper mItemTouchHelper = new ItemTouchHelper(mItemTouchCallback);
}