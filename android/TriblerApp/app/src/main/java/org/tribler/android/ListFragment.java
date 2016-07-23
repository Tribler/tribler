package org.tribler.android;

import android.content.Context;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import java.util.ArrayList;

import butterknife.BindView;
import butterknife.ButterKnife;
import butterknife.Unbinder;

/**
 * A fragment representing a list of {@link TriblerChannel} and {@link TriblerTorrent}.
 * Activities containing this fragment MUST implement the {@link IListFragmentInteractionListener}
 * interface.
 */
public class ListFragment extends RetrofitFragment {

    @BindView(R.id.list_recycler_view)
    RecyclerView mRecyclerView;

    private Unbinder mUnbinder;
    private IListFragmentInteractionListener mListener;
    protected FilterableRecyclerViewAdapter mAdapter;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        if (context instanceof IListFragmentInteractionListener) {
            mListener = (IListFragmentInteractionListener) context;
        } else {
            mListener = null;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_list_fast_scroller, container, false);
        mUnbinder = ButterKnife.bind(this, view);

        // Optimize performance
        mRecyclerView.setHasFixedSize(true);

        mAdapter = new TriblerViewAdapter(new ArrayList<>(), mListener, mListener);
        mRecyclerView.setAdapter(mAdapter);

        return view;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        super.onDestroyView();
        mRecyclerView.setAdapter(null);
        mAdapter = null;
        mUnbinder.unbind();
        mUnbinder = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        mListener = null;
    }

    /**
     * This interface must be implemented by activities that contain this
     * fragment to allow an interaction in this fragment to be communicated
     * to the activity and potentially other fragments contained in that
     * activity.
     */
    public interface IListFragmentInteractionListener extends TriblerViewAdapter.OnClickListener, TriblerViewAdapter.OnSwipeListener {
    }
}
