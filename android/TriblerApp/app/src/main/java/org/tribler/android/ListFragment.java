package org.tribler.android;

import android.content.Context;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import java.util.ArrayList;

import butterknife.BindView;
import butterknife.ButterKnife;
import butterknife.Unbinder;
import xyz.danoz.recyclerviewfastscroller.vertical.VerticalRecyclerViewFastScroller;

/**
 * A fragment representing a list of {@link TriblerChannel} and {@link TriblerTorrent}.
 * Activities containing this fragment MUST implement the {@link IListFragmentInteractionListener}
 * interface.
 */
public class ListFragment extends RetrofitFragment {

    @BindView(R.id.list_recycler_view)
    RecyclerView recyclerView;

    @BindView(R.id.list_fast_scroller)
    VerticalRecyclerViewFastScroller fastScroller;

    private Unbinder _unbinder;
    protected IListFragmentInteractionListener interactionListener;
    protected FilterableRecyclerViewAdapter adapter;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        if (context instanceof IListFragmentInteractionListener) {
            interactionListener = (IListFragmentInteractionListener) context;
        } else {
            interactionListener = null;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        interactionListener = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_list_fast_scroller, container, false);
        _unbinder = ButterKnife.bind(this, view);

        // Optimize performance
        recyclerView.setHasFixedSize(true);

        // Let the recycler view show the adapter list
        adapter = new TriblerViewAdapter(new ArrayList<>(), interactionListener, interactionListener);
        recyclerView.setAdapter(adapter);

        // Let the fast scroller scroll the recycler view
        fastScroller.setRecyclerView(recyclerView);
        // Let the recycler view scroll the scroller's handle
        recyclerView.addOnScrollListener(fastScroller.getOnScrollListener());
        // Scroll to the current position of the layout manager
        //setRecyclerViewLayoutManager(recyclerView);

        return view;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        super.onDestroyView();
        recyclerView.setAdapter(null);
        adapter = null;
        _unbinder.unbind();
        _unbinder = null;
    }

    /**
     * @param recyclerView Set the LayoutManager of this RecycleView
     */
    private void setRecyclerViewLayoutManager(RecyclerView recyclerView) {
        int scrollPosition = 0;
        LinearLayoutManager linearLayoutManager = (LinearLayoutManager) recyclerView.getLayoutManager();
        // If a layout manager has already been set, get current scroll position
        if (linearLayoutManager != null) {
            scrollPosition = linearLayoutManager.findFirstCompletelyVisibleItemPosition();
        } else {
            linearLayoutManager = new LinearLayoutManager(getActivity());
            recyclerView.setLayoutManager(linearLayoutManager);
        }
        recyclerView.scrollToPosition(scrollPosition);
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
