package org.tribler.android;

import android.content.Context;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.util.ArrayList;

import butterknife.BindView;
import xyz.danoz.recyclerviewfastscroller.vertical.VerticalRecyclerViewFastScroller;

/**
 * A fragment representing a list of {@link TriblerChannel} and {@link TriblerTorrent}.
 * Activities containing this fragment MUST implement the {@link IListFragmentInteractionListener}
 * interface.
 */
public class ListFragment extends ViewFragment {

    @BindView(R.id.list_recycler_view)
    RecyclerView recyclerView;

    @BindView(R.id.list_fast_scroller)
    VerticalRecyclerViewFastScroller fastScroller;

    @BindView(R.id.list_progress)
    View progressView;

    @BindView(R.id.list_progress_status)
    TextView statusBar;

    protected TriblerViewAdapter adapter;
    protected IListFragmentInteractionListener interactionListener;

    public TriblerViewAdapter getAdapter() {
        return adapter;
    }

    @Nullable
    public IListFragmentInteractionListener getListInteractionListener() {
        return interactionListener;
    }

    /**
     * @param listener IListFragmentInteractionListener that will listen to the adapter events
     */
    public void setListInteractionListener(@Nullable IListFragmentInteractionListener listener) {
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
        // Side effects:
        setListInteractionListener(getListInteractionListener());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();

        setListInteractionListener(null);

        adapter = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);

        if (context instanceof IListFragmentInteractionListener) {
            setListInteractionListener((IListFragmentInteractionListener) context);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();

        setListInteractionListener(null);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_list_fast_scroller, container, false);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onViewCreated(View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        // Optimize performance
        recyclerView.setHasFixedSize(true);
        // Let the recycler view show the adapter list
        recyclerView.setAdapter(adapter);
        // Let the fast scroller scroll the recycler view
        fastScroller.setRecyclerView(recyclerView);
        // Let the recycler view scroll the scroller's handle
        recyclerView.addOnScrollListener(fastScroller.getOnScrollListener());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        recyclerView.setAdapter(null);
        super.onDestroyView();
    }

    protected void reload() {
        adapter.clear();
        showLoading(true);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void showLoading(@Nullable CharSequence text) {
        super.showLoading(text);
        if (progressView == null) {
            /** @see super.onViewCreated
             */
            return;
        }
        if (text == null) {
            progressView.setVisibility(View.GONE);
        } else {
            statusBar.setText(text);
            progressView.setVisibility(View.VISIBLE);
        }
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
