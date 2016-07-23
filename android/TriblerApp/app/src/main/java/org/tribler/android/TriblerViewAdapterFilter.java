package org.tribler.android;

import android.text.TextUtils;
import android.widget.Filter;

import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;

/**
 * Filter channel name, channel description, torrent name, torrent category
 */
public class TriblerViewAdapterFilter extends Filter {

    private FilterableRecyclerViewAdapter mAdapter;
    private List<Object> mDataList;

    public TriblerViewAdapterFilter(FilterableRecyclerViewAdapter adapter, List<Object> list) {
        super();
        mAdapter = adapter;
        mDataList = list;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected ObjectListFilterResults performFiltering(CharSequence constraint) {
        // Copy data list to avoid concurrency issues while iterating over it
        LinkedList<Object> dataList = new LinkedList<>(mDataList);
        List<Object> filteredList = new ArrayList<>();
        // Sanitize query
        String query = constraint.toString().trim().toLowerCase();
        if (TextUtils.isEmpty(query)) {
            // Show all
            filteredList.addAll(dataList);
        }
        // Filter by name and description
        else {
            for (Object item : dataList) {
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
            ObjectListFilterResults listResults = (ObjectListFilterResults) results;
            mAdapter.setList(listResults.values);
        }
    }

    protected static class ObjectListFilterResults extends FilterResults {

        public List<Object> values;
    }
}
