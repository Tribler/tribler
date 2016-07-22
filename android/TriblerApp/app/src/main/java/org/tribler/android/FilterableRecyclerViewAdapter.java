package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.widget.Filter;
import android.widget.Filterable;

import java.util.ArrayList;
import java.util.List;

public abstract class FilterableRecyclerViewAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> implements Filterable {

    private List<Object> mDataList;
    private List<Object> mFilteredDataList;
    private TriblerViewAdapterFilter mFilter;

    public FilterableRecyclerViewAdapter() {
        mDataList = new ArrayList<>();
        mFilteredDataList = new ArrayList<>();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Filter getFilter() {
        if (mFilter == null) {
            mFilter = new TriblerViewAdapterFilter(this, mDataList);
        }
        return mFilter;
    }

    /**
     * @param adapterPosition The position in the adapter list
     * @return The item on the given adapter position
     */
    public Object getItem(int adapterPosition) {
        return mFilteredDataList.get(adapterPosition);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public int getItemCount() {
        return mFilteredDataList.size();
    }

    /**
     * @param item The item to add to the adapter list
     * @return True if the item is successfully added, false otherwise
     */
    public boolean addItem(Object item) {
        boolean added = mDataList.add(item);
        if (added) {
            insertItem(getItemCount(), item);
        }
        return added;
    }

    /**
     * @param item The item to remove from the adapter list
     * @return True if the item is successfully removed, false otherwise
     */
    public boolean removeItem(Object item) {
        boolean removed = mDataList.remove(item);
        if (removed) {
            int adapterPosition = mFilteredDataList.indexOf(item);
            if (adapterPosition >= 0) {
                removeItem(adapterPosition);
            }
        }
        return removed;
    }

    /**
     * Empty data list
     */
    public void clear() {
        mDataList.clear();
        mFilteredDataList.clear();
        notifyDataSetChanged();
    }

    public void setList(List<Object> list) {
        applyAndAnimateRemovals(list);
        applyAndAnimateAdditions(list);
        applyAndAnimateMovedItems(list);
    }

    private void applyAndAnimateRemovals(List<Object> list) {
        for (int i = mFilteredDataList.size() - 1; i >= 0; i--) {
            Object item = mFilteredDataList.get(i);
            if (!list.contains(item)) {
                removeItem(i);
            }
        }
    }

    private void applyAndAnimateAdditions(List<Object> list) {
        for (int i = 0, count = list.size(); i < count; i++) {
            Object item = list.get(i);
            if (!mFilteredDataList.contains(item)) {
                insertItem(i, item);
            }
        }
    }

    private void applyAndAnimateMovedItems(List<Object> list) {
        for (int toPosition = list.size() - 1; toPosition >= 0; toPosition--) {
            Object item = list.get(toPosition);
            int fromPosition = mFilteredDataList.indexOf(item);
            if (fromPosition >= 0 && fromPosition != toPosition) {
                moveItem(fromPosition, toPosition);
            }
        }
    }

    /**
     * @param adapterPosition The position of the item in adapter list to remove
     */
    private void removeItem(int adapterPosition) {
        mFilteredDataList.remove(adapterPosition);
        notifyItemRemoved(adapterPosition);
    }

    /**
     * @param adapterPosition The position in the adapter list of where to insert the item
     * @param item            The item to insert to the adapter list
     */
    private void insertItem(int adapterPosition, Object item) {
        mFilteredDataList.add(adapterPosition, item);
        notifyItemInserted(adapterPosition);
    }

    /**
     * @param fromPosition The position in the adapter list of the item to move from
     * @param toPosition   The position in the adapter list of the item to move to
     */
    private void moveItem(int fromPosition, int toPosition) {
        Object model = mFilteredDataList.remove(fromPosition);
        mFilteredDataList.add(toPosition, model);
        notifyItemMoved(fromPosition, toPosition);
    }

    /**
     * @param item The item to refresh the view of in the adapter list
     * @return True if the view of the item is successfully refreshed, false otherwise
     */
    public boolean itemChanged(Object item) {
        int adapterPosition = mFilteredDataList.indexOf(item);
        if (adapterPosition < 0) {
            return false;
        }
        notifyItemChanged(adapterPosition);
        return true;
    }

}
