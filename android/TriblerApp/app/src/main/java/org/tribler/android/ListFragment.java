package org.tribler.android;

import android.content.Context;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

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
    protected TriblerViewAdapter adapter;

    public IListFragmentInteractionListener getInteractionListener() {
        return interactionListener;
    }

    public void setInteractionListener(IListFragmentInteractionListener listener) {
        interactionListener = listener;
        // onAttach is called before onCreate
        if (adapter != null) {
            adapter.setClickListener(interactionListener);
            adapter.setSwipeListener(interactionListener);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        adapter = new TriblerViewAdapter(new ArrayList<>());
        adapter.setClickListener(interactionListener);
        adapter.setSwipeListener(interactionListener);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        adapter = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        if (context instanceof IListFragmentInteractionListener) {
            setInteractionListener((IListFragmentInteractionListener) context);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        setInteractionListener(null);
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
        recyclerView.setAdapter(adapter);
        // Let the fast scroller scroll the recycler view
        fastScroller.setRecyclerView(recyclerView);
        // Let the recycler view scroll the scroller's handle
        recyclerView.addOnScrollListener(fastScroller.getOnScrollListener());

        return view;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        super.onDestroyView();
        recyclerView.setAdapter(null);
        _unbinder.unbind();
        _unbinder = null;
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
