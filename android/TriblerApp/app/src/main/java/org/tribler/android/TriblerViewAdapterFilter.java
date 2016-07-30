package org.tribler.android;

import android.text.TextUtils;
import android.widget.Filter;

import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.util.Collection;
import java.util.HashSet;
import java.util.LinkedList;

/**
 * Filter channel name, channel description, torrent name, torrent category
 */
public class TriblerViewAdapterFilter extends Filter {

    private final FilterableRecyclerViewAdapter _adapter;

    public TriblerViewAdapterFilter(FilterableRecyclerViewAdapter adapter) {
        super();
        _adapter = adapter;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected FilterResults performFiltering(CharSequence constraint) {
        // Get a copy of the data to avoid concurrency issues while iterating over it
        HashSet<Object> data = _adapter.getData();
        Collection<Object> filtered = new LinkedList<>();
        // Sanitize query
        String query = constraint.toString().trim().toLowerCase();
        if (TextUtils.isEmpty(query)) {
            // Show all
            filtered = data;
        }
        // Filter by name and description
        else {
            for (Object object : data) {
                if (object instanceof TriblerChannel) {
                    TriblerChannel channel = (TriblerChannel) object;
                    if (channel.getName().toLowerCase().contains(constraint)
                            || channel.getDescription().toLowerCase().contains(constraint)) {
                        filtered.add(channel);
                    }
                } else if (object instanceof TriblerTorrent) {
                    TriblerTorrent torrent = (TriblerTorrent) object;
                    if (torrent.getName().toLowerCase().contains(constraint)
                            || torrent.getCategory().toLowerCase().contains(constraint)) {
                        filtered.add(torrent);
                    }
                }
            }
        }
        CollectionFilterResults results = new CollectionFilterResults();
        results.collection = filtered;
        return results;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void publishResults(CharSequence constraint, FilterResults filterResults) {
        if (filterResults instanceof CollectionFilterResults) {
            CollectionFilterResults results = (CollectionFilterResults) filterResults;
            _adapter.onFilterResults(results.collection);
        }
    }

    protected static class CollectionFilterResults extends FilterResults {

        public Collection<Object> collection;
    }
}
