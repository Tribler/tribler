package org.tribler.android;

import android.text.TextUtils;
import android.widget.Filter;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedList;
import java.util.List;

/**
 * Filter channel name, channel description, torrent name, torrent category
 */
public class TriblerViewAdapterFilter extends Filter {

    private final FilterableRecyclerViewAdapter _adapter;
    private final Collection<Object> _objects;

    public TriblerViewAdapterFilter(FilterableRecyclerViewAdapter adapter, Collection<Object> objects) {
        super();
        _adapter = adapter;
        _objects = objects;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected FilterResults performFiltering(CharSequence constraint) {
        // Copy data list to avoid concurrency issues while iterating over it
        ArrayList<Object> dataList = new ArrayList<>(_objects);
        List<Object> filteredList = new LinkedList<>();
        // Sanitize query
        String query = constraint.toString().trim().toLowerCase();
        if (TextUtils.isEmpty(query)) {
            // Show all
            filteredList = dataList;
        }
        // Filter by name and description
        else {
            for (Object object : dataList) {
                if (object instanceof TriblerChannel) {
                    TriblerChannel channel = (TriblerChannel) object;
                    if (channel.getName().toLowerCase().contains(constraint)
                            || channel.getDescription().toLowerCase().contains(constraint)) {
                        filteredList.add(channel);
                    }
                } else if (object instanceof TriblerTorrent) {
                    TriblerTorrent torrent = (TriblerTorrent) object;
                    if (torrent.getName().toLowerCase().contains(constraint)
                            || torrent.getCategory().toLowerCase().contains(constraint)) {
                        filteredList.add(torrent);
                    }
                }
            }
        }
        ObjectListFilterResults results = new ObjectListFilterResults();
        results.values = filteredList;
        results.count = filteredList.size();
        return results;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void publishResults(CharSequence constraint, FilterResults results) {
        if (results instanceof ObjectListFilterResults) {
            ObjectListFilterResults list = (ObjectListFilterResults) results;
            _adapter.onFilterResults(list.values, results.count);
        }
    }

    protected static class ObjectListFilterResults extends FilterResults {

        public List<Object> values;
    }
}
