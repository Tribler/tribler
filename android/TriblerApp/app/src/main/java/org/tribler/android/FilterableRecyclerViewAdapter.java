package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.widget.Filter;
import android.widget.Filterable;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;

public abstract class FilterableRecyclerViewAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> implements Filterable {

    private final HashSet<Object> _dataSet;
    private final ArrayList<Object> _filteredDataList;
    private TriblerViewAdapterFilter _filter;

    public FilterableRecyclerViewAdapter(Collection<Object> objects) {
        _dataSet = new HashSet<>(objects);
        _filteredDataList = new ArrayList<>(objects);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Filter getFilter() {
        if (_filter == null) {
            _filter = new TriblerViewAdapterFilter(this, _dataSet);
        }
        return _filter;
    }

    /**
     * Replace filtered data list with results
     *
     * @param results Collection of filtered objects
     * @param count   Amount of filtered objects
     */
    public void onFilterResults(Collection<Object> results, int count) {
        _filteredDataList.clear();
        _filteredDataList.addAll(results);
        notifyDataSetChanged();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int getItemCount() {
        return _filteredDataList.size();
    }

    /**
     * Remove all data
     */
    public void clear() {
        _dataSet.clear();
        _filteredDataList.clear();
        notifyDataSetChanged();
    }

    /**
     * @param object The object to add to the adapter list
     * @return True if the object is successfully added, false otherwise
     */
    public boolean addObject(Object object) {
        boolean added = _dataSet.add(object);
        if (added) {
            insertItem(getItemCount(), object);
        }
        return added;
    }

    /**
     * @param object The object to remove from the adapter list
     * @return True if the object is successfully removed, false otherwise
     */
    public boolean removeObject(Object object) {
        boolean removed = _dataSet.remove(object);
        if (removed) {
            int adapterPosition = _filteredDataList.indexOf(object);
            if (adapterPosition != -1) {
                removeItem(adapterPosition);
            }
        }
        return removed;
    }

    /**
     * @param object The object to refresh the view of in the adapter list
     * @return True if the view of the item is successfully refreshed, false otherwise
     */
    public boolean notifyObjectChanged(Object object) {
        int adapterPosition = _filteredDataList.indexOf(object);
        if (adapterPosition != -1) {
            notifyItemChanged(adapterPosition);
            return true;
        }
        return false;
    }

    /**
     * @param adapterPosition The position in the adapter list
     * @return The object on the given adapter position
     */
    protected Object getObject(int adapterPosition) {
        return _filteredDataList.get(adapterPosition);
    }

    /**
     * @param adapterPosition The position in the adapter list of where to insert the item
     * @param item            The item to insert to the adapter list
     */
    private void insertItem(int adapterPosition, Object item) {
        _filteredDataList.add(adapterPosition, item);
        notifyItemInserted(adapterPosition);
    }

    /**
     * @param adapterPosition The position of the item in adapter list to remove
     */
    private void removeItem(int adapterPosition) {
        _filteredDataList.remove(adapterPosition);
        notifyItemRemoved(adapterPosition);
    }

    /**
     * @param fromPosition The position in the adapter list of the item to move from
     * @param toPosition   The position in the adapter list of the item to move to
     */
    private void moveItem(int fromPosition, int toPosition) {
        Object model = _filteredDataList.remove(fromPosition);
        _filteredDataList.add(toPosition, model);
        notifyItemMoved(fromPosition, toPosition);
    }
}
