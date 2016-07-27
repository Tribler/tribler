package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.widget.SearchView;
import android.text.TextUtils;
import android.view.Menu;
import android.view.MenuItem;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import java.util.concurrent.TimeUnit;

import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;

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

            if (!TextUtils.isEmpty(query)) {

                // Show voice search query
                SearchView searchView = (SearchView) findViewById(R.id.search_view);
                if (searchView != null && searchView.getQuery() != query) {
                    searchView.setQuery(query, false);
                    searchView.clearFocus();
                }

                // Start search
                SearchFragment searchFragment =
                        (SearchFragment) getSupportFragmentManager().findFragmentById(R.id.fragment_search);
                searchFragment.startSearch(query);
            }
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
        MenuItem btnSearch = menu.findItem(R.id.search_view);
        SearchView searchView = (SearchView) btnSearch.getActionView();
        // Set hint and enable voice search
        SearchManager searchManager =
                (SearchManager) getApplicationContext().getSystemService(Context.SEARCH_SERVICE);
        searchView.setSearchableInfo(searchManager.getSearchableInfo(getComponentName()));
        // Show search input field
        searchView.setIconified(false);
        // Never close search view
        searchView.setOnCloseListener(() -> {
            // Override default behaviour with return true
            return true;
        });
        // Restore last query
        String query = getIntent().getStringExtra(SearchManager.QUERY);
        if (searchView.getQuery() != query && !TextUtils.isEmpty(query)) {
            searchView.setQuery(query, false);
            searchView.clearFocus();
        }

        // Start search on query text change with debounce
        rxSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .debounce(400, TimeUnit.MILLISECONDS)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        String query = event.queryText().toString();
                        String current = getIntent().getStringExtra(SearchManager.QUERY);

                        if (!query.equals(current) && !TextUtils.isEmpty(query)) {
                            // Replace current intent
                            Intent intent = new Intent(SearchActivity.this, SearchActivity.class);
                            intent.setAction(Intent.ACTION_SEARCH);
                            intent.putExtra(SearchManager.QUERY, query);
                            onNewIntent(intent);
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                    }
                }));

        return true;
    }
}
