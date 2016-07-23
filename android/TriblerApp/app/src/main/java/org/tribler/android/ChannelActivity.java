package org.tribler.android;

import android.app.FragmentManager;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.Toolbar;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;

import xyz.danoz.recyclerviewfastscroller.vertical.VerticalRecyclerViewFastScroller;

public class ChannelActivity extends AppCompatActivity {

    public static final String EXTRA_DISPERSY_CID = "dispersy.CID";

    private ChannelFragment getFragment() {
        FragmentManager fm = getFragmentManager();
        ChannelFragment fragment = (ChannelFragment) fm.findFragmentByTag(ChannelFragment.TAG);
        // If not retained (or first time running), we need to create it
        if (fragment == null) {
            fragment = new ChannelFragment();
            // Tell the framework to try to keep this fragment around during a configuration change
            fragment.setRetainInstance(true);
            fm.beginTransaction().add(fragment, ChannelFragment.TAG).commit();
        }
        return fragment;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        initGui();
        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (Intent.ACTION_GET_CONTENT.equals(intent.getAction())) {
            String cid = intent.getStringExtra(EXTRA_DISPERSY_CID);
            getFragment().getTorrents(cid);

            // Set title
            String title = intent.getStringExtra(Intent.EXTRA_TITLE);
            ActionBar actionbar = getSupportActionBar();
            assert actionbar != null;
            actionbar.setTitle(title);
        }
    }

    private void initGui() {
        setContentView(R.layout.activity_channel);

        // Set action toolbar
        Toolbar toolbar = (Toolbar) findViewById(R.id.activity_channel_toolbar);
        assert toolbar != null;
        setSupportActionBar(toolbar);
        ActionBar actionbar = getSupportActionBar();
        assert actionbar != null;
        actionbar.setDisplayHomeAsUpEnabled(true);

        // Set list view
        RecyclerView recyclerView = (RecyclerView) findViewById(R.id.list_recycler_view);
        assert recyclerView != null;
        // Improve performance
        recyclerView.setHasFixedSize(true);

        // Set fast scroller
        VerticalRecyclerViewFastScroller fastScroller = (VerticalRecyclerViewFastScroller) findViewById(R.id.list_fast_scroller);
        assert fastScroller != null;
        // Connect the recycler to the scroller (to let the scroller scroll the list)
        fastScroller.setRecyclerView(recyclerView);
        // Connect the scroller to the recycler (to let the recycler scroll the scroller's handle)
        recyclerView.addOnScrollListener(fastScroller.getOnScrollListener());
        // Scroll to the current position of the layout manager
        setRecyclerViewLayoutManager(recyclerView);
    }

    /**
     * @param recyclerView Set the LayoutManager of this RecycleView
     */
    private void setRecyclerViewLayoutManager(RecyclerView recyclerView) {
        int scrollPosition = 0;
        LinearLayoutManager linearLayoutManager = (LinearLayoutManager) recyclerView.getLayoutManager();
        // If a layout manager has already been set, get current scroll position.
        if (linearLayoutManager != null) {
            scrollPosition = linearLayoutManager.findFirstCompletelyVisibleItemPosition();
        } else {
            linearLayoutManager = new LinearLayoutManager(this);
            recyclerView.setLayoutManager(linearLayoutManager);
        }
        recyclerView.scrollToPosition(scrollPosition);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar if it is present
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.activity_channel_action_bar, menu);

        // Search button
        MenuItem btnSearch = menu.findItem(R.id.btn_search);
        assert btnSearch != null;
        final SearchView searchView = (SearchView) btnSearch.getActionView();
        searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextSubmit(String query) {
                return false;
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextChange(String query) {
                getFragment().mAdapter.getFilter().filter(query);
                return true;
            }
        });

        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onBackPressed() {
        SearchView searchView = (SearchView) findViewById(R.id.btn_search);
        // Close search if open
        if (searchView != null && !searchView.isIconified()) {
            searchView.setIconified(true);
        } else {
            super.onBackPressed();
        }
    }
}
