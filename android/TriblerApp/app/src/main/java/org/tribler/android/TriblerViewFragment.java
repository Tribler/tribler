package org.tribler.android;

import android.app.Fragment;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.view.View;

public abstract class TriblerViewFragment extends Fragment implements TriblerViewAdapter.OnClickListener, TriblerViewAdapter.OnSwipeListener {

    protected TriblerViewAdapter mAdapter;
    private RecyclerView mRecyclerView;

    /**
     * {@inheritDoc}
     */
    @Nullable
    @Override
    public View getView() {
        return mRecyclerView;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mAdapter = new TriblerViewAdapter();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityCreated(Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);
        mRecyclerView = (RecyclerView) getActivity().findViewById(R.id.search_results_list);
        mAdapter.attachToRecyclerView(mRecyclerView);
        mAdapter.setOnClickListener(this);
        mAdapter.setOnSwipeListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        mRecyclerView = null;
        mAdapter.attachToRecyclerView(null);
        mAdapter.setOnClickListener(null);
        mAdapter.setOnSwipeListener(null);
    }

}
