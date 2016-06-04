package org.tribler.android;

import android.widget.Filter;

import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;

/**
 * Filter channel name, channel description, torrent name, torrent category
 */
public class TriblerViewAdapterFilter extends Filter {

    private TriblerViewAdapter mAdapter;
    private List<Object> mOriginalList;

    public TriblerViewAdapterFilter(TriblerViewAdapter adapter, List<Object> original) {
        super();
        mAdapter = adapter;
        mOriginalList = new LinkedList<>(original);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected Filter.FilterResults performFiltering(CharSequence query) {
        List<Object> filteredList = new ArrayList<>();
        String constraint = query.toString().trim().toLowerCase();
        if (constraint.isEmpty()) {
            filteredList.addAll(mOriginalList);
        } else {
            for (Object item : mOriginalList) {
                if (item instanceof TriblerChannel) {
                    TriblerChannel channel = (TriblerChannel) item;
                    if (channel.getName().toLowerCase().contains(constraint)
                            || channel.getDescription().toLowerCase().contains(constraint)) {
                        filteredList.add(channel);
                    }
                } else if (item instanceof TriblerTorrent) {
                    TriblerTorrent torrent = (TriblerTorrent) item;
                    if (torrent.getName().toLowerCase().contains(constraint)
                            || torrent.getCategory().toLowerCase().contains(constraint)) {
                        filteredList.add(torrent);
                    }
                }
            }
        }
        FilterResults results = new FilterResults();
        results.values = filteredList;
        results.count = filteredList.size();
        return results;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void publishResults(CharSequence filterPattern, FilterResults filterResults) {
        List<Object> filteredList = (List<Object>) filterResults.values;
        mAdapter.animateTo(filteredList);
    }
}
