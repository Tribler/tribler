package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.Toolbar;
import android.text.TextUtils;
import android.view.Menu;
import android.view.MenuItem;

import butterknife.BindView;

public class SearchActivity extends BaseActivity {

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_search);
        handleIntent(getIntent());
    }

    protected void handleIntent(Intent intent) {
        if (Intent.ACTION_SEARCH.equals(intent.getAction())) {
            String query = intent.getStringExtra(SearchManager.QUERY);

            // Show voice search query
            SearchView searchView = (SearchView) findViewById(R.id.btn_search);
            if (searchView != null) {
                searchView.setQuery(query, false);
                searchView.clearFocus();
            }

            // Start search
            SearchFragment searchFragment = (SearchFragment)
                    getFragmentManager().findFragmentById(R.id.fragment_search);
            searchFragment.startSearch(query);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar (if it is present)
        getMenuInflater().inflate(R.menu.menu_search, menu);

        // Search button
        MenuItem btnSearch = menu.findItem(R.id.btn_search);
        SearchView searchView = (SearchView) btnSearch.getActionView();
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
        searchView.setOnCloseListener(() -> {
            // Override default behaviour with return true
            return true;
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
