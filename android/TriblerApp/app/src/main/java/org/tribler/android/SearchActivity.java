package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.Toolbar;
import android.text.TextUtils;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;

import xyz.danoz.recyclerviewfastscroller.vertical.VerticalRecyclerViewFastScroller;

public class SearchActivity extends AppCompatActivity {

    SearchView searchView;

    public SearchFragment createFragment() {
        SearchFragment fragment = new SearchFragment();
        String tag = fragment.getClass().toString();
        getFragmentManager().beginTransaction().addToBackStack(tag)
                .replace(R.id.content, fragment, tag)
                .commit();
        return fragment;
    }

    /**
     * {@inheritDoc}
     */
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
        if (Intent.ACTION_SEARCH.equals(intent.getAction())) {
            String query = intent.getStringExtra(SearchManager.QUERY);
            // Show voice search query
            if (searchView != null) {
                searchView.setQuery(query, false);
                searchView.clearFocus();
            }
            createFragment().startSearch(query);
        }
    }

    private void initGui() {
        setContentView(R.layout.activity_search);

        // Set action toolbar
        Toolbar toolbar = (Toolbar) findViewById(R.id.activity_search_toolbar);
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
        inflater.inflate(R.menu.menu_search, menu);

        // Search button
        MenuItem btnSearch = menu.findItem(R.id.btn_search);
        assert btnSearch != null;
        searchView = (SearchView) btnSearch.getActionView();
        // Set hint and enable voice search
        SearchManager searchManager = (SearchManager) getSystemService(Context.SEARCH_SERVICE);
        searchView.setSearchableInfo(searchManager.getSearchableInfo(getComponentName()));
        // Show search input field
        searchView.setIconified(false);
        // Restore last query
        String query = getIntent().getStringExtra(SearchManager.QUERY);
        if (!TextUtils.isEmpty(query)) {
            searchView.setQuery(query, false);
            searchView.clearFocus();
        }
        // Never close search view
        searchView.setOnCloseListener(new SearchView.OnCloseListener() {
            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onClose() {
                // Override default behaviour with return true
                return true;
            }
        });
        // Search on submit
        searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextSubmit(String query) {
                Intent intent = new Intent(SearchActivity.this, SearchActivity.class);
                intent.setAction(Intent.ACTION_SEARCH);
                intent.putExtra(SearchManager.QUERY, query);
                onNewIntent(intent);
                return true;
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextChange(String newText) {
                return false;
            }
        });

        return true;
    }
}
