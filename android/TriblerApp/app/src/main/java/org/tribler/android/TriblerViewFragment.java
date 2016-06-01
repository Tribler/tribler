package org.tribler.android;

import android.app.Fragment;
import android.os.Bundle;
import android.support.v7.widget.RecyclerView;

public class TriblerViewFragment extends Fragment {

    protected TriblerViewAdapter mAdapter;

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
        RecyclerView recyclerView = (RecyclerView) getActivity().findViewById(R.id.search_results_list);
        mAdapter.attachToRecyclerView(recyclerView);
        mAdapter.setOnClickListener((TriblerViewAdapter.OnClickListener) getActivity());
        mAdapter.setOnSwipeListener((TriblerViewAdapter.OnSwipeListener) getActivity());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        mAdapter.attachToRecyclerView(null);
        mAdapter.setOnClickListener(null);
        mAdapter.setOnSwipeListener(null);
    }

}
