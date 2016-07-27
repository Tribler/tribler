package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.widget.SearchView;
import android.view.Menu;
import android.view.MenuItem;
import android.widget.Filter;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;

public class ChannelActivity extends BaseActivity {

    public static final String EXTRA_DISPERSY_CID = "org.tribler.android.dispersy.CID";

    private ChannelFragment _fragment;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_channel);

        _fragment = (ChannelFragment) getSupportFragmentManager().findFragmentById(R.id.fragment_channel);
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

    protected void handleIntent(Intent intent) {
        if (Intent.ACTION_GET_CONTENT.equals(intent.getAction())) {
            String dispersyCid = intent.getStringExtra(EXTRA_DISPERSY_CID);

            // Get torrents for channel
            _fragment.loadTorrents(dispersyCid);

            // Set title
            ActionBar actionBar = getSupportActionBar();
            if (actionBar != null) {
                actionBar.setTitle(intent.getStringExtra(Intent.EXTRA_TITLE));
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
        getMenuInflater().inflate(R.menu.menu_channel, menu);

        // Search button
        MenuItem btnFilter = menu.findItem(R.id.btn_filter);
        SearchView searchView = (SearchView) btnFilter.getActionView();

        // Set search hint
        searchView.setQueryHint(getText(R.string.action_search_in_channel));

        // Get list filter
        final Filter filter = _fragment.getAdapter().getFilter();

        // Filter on query text change
        rxSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        filter.filter(event.queryText().toString());
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                    }
                }));

        return true;
    }
}
