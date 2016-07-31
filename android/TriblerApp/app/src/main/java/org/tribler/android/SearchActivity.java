package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.widget.SearchView;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import java.util.concurrent.TimeUnit;

import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;

public class SearchActivity extends BaseActivity {

    private SearchFragment _fragment;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_search);

        _fragment = (SearchFragment) getSupportFragmentManager().findFragmentById(R.id.fragment_search);
        _fragment.setRetainInstance(true);

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        _fragment = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);

        SearchView searchView = (SearchView) findViewById(R.id.search_view);
        if (searchView != null) {

            String query = intent.getStringExtra(SearchManager.QUERY);
            CharSequence current = searchView.getQuery();

            if (!TextUtils.isEmpty(query) && !query.equals(current)) {
                // Show voice search query
                searchView.setQuery(query, false);

                if (TextUtils.isEmpty(current)) {
                    // Close keyboard on voice search submit
                    searchView.clearFocus();
                }
            }
        }
    }

    protected void handleIntent(Intent intent) {
        if (Intent.ACTION_SEARCH.equals(intent.getAction())) {
            String query = intent.getStringExtra(SearchManager.QUERY);

            if (!TextUtils.isEmpty(query)) {
                // Start search
                _fragment.startSearch(query);
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

        String query = getIntent().getStringExtra(SearchManager.QUERY);
        CharSequence current = searchView.getQuery();

        if (!TextUtils.isEmpty(query) && !query.equals(current)) {
            // Restore last query
            searchView.setQuery(query, false);
            searchView.clearFocus();
        }

        // Start search on query text change with debounce
        rxSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .debounce(600, TimeUnit.MILLISECONDS)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        CharSequence query = event.queryText();
                        String current = getIntent().getStringExtra(SearchManager.QUERY);

                        if (!TextUtils.isEmpty(query) && !query.equals(current)) {
                            // Fire new search intent
                            Intent searchIntent = new Intent(SearchActivity.this, SearchActivity.class);
                            searchIntent.setAction(Intent.ACTION_SEARCH);
                            searchIntent.putExtra(SearchManager.QUERY, query.toString());
                            onNewIntent(searchIntent);
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onCreateOptionsMenu", "SearchViewQueryTextEvent", e);
                    }
                }));

        return true;
    }
}
