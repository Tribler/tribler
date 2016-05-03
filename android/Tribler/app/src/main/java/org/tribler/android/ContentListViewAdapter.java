package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import java.util.List;

/**
 * Creates visual representation for channels and videos in a list.
 */
public class ContentListViewAdapter extends RecyclerView.Adapter<ContentListViewAdapter.AbstractContentViewHolder> {

    private static final int VIEW_TYPE_CHANNEL = 1;
    private static final int VIEW_TYPE_TORRENT = 2;

    private List<AbstractContent> mData;

    @Override
    public int getItemViewType(int position) {
        if (mData.get(position) instanceof TriblerChannel) {
            return VIEW_TYPE_CHANNEL;
        }
        return VIEW_TYPE_TORRENT;
    }

    abstract class AbstractContentViewHolder extends RecyclerView.ViewHolder {
        public TextView title, description;
        public ImageView image;

        public AbstractContentViewHolder(View itemView) {
            super(itemView);
            title = (TextView) itemView.findViewById(R.id.title);
            description = (TextView) itemView.findViewById(R.id.description);
            image = (ImageView) itemView.findViewById(R.id.image);
        }
    }

    public class ChannelViewHolderAbstract extends AbstractContentViewHolder {
        public TextView videosCount;

        public ChannelViewHolderAbstract(View itemView) {
            super(itemView);
            videosCount = (TextView) itemView.findViewById(R.id.videosCount);
        }
    }

    public class VideoViewHolderAbstract extends AbstractContentViewHolder {
        public TextView duration;
        public TextView bitrate;

        public VideoViewHolderAbstract(View itemView) {
            super(itemView);
            duration = (TextView) itemView.findViewById(R.id.duration);
            bitrate = (TextView) itemView.findViewById(R.id.bitrate);
        }
    }

    public ContentListViewAdapter(List<AbstractContent> mData) {
        this.mData = mData;
    }

    @Override
    /**
     * @param parent    The group to which the view should be added
     * @param viewType  The
     */
    public AbstractContentViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        // Create a new view
        View itemView = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.list_item_video, parent, false);

        return new AbstractContentViewHolder(itemView);
    }

    @Override
    /**
     * Replaces the contents of a view (invoked by the layout manager)
     * @param holder    The holder of the view of an item
     * @param position  The position of the item in the data set
     */
    public void onBindViewHolder(AbstractContentViewHolder holder, int position) {
        TorrentItem torrentItem = mData.get(position);
        holder.title.setText(torrentItem.getTitle());
        holder.description.setText(torrentItem.getDescription());
        holder.duration.setText(torrentItem.getDuration());
    }

    @Override
    /**
     * @return The amount of items in the data set (invoked by the layout manager)
     */
    public int getItemCount() {
        return mData.size();
    }
}