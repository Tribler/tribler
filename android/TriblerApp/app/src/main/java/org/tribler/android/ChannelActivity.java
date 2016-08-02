package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.widget.SearchView;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import rx.Observer;

public class ChannelActivity extends BaseActivity {

    public static final String ACTION_TOGGLE_SUBSCRIBED = "org.tribler.android.TOGGLE_SUBSCRIBED";
    public static final String EXTRA_SUBSCRIBED = "org.tribler.android.SUBSCRIBED";
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

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar (if it is present)
        getMenuInflater().inflate(R.menu.activity_channel_menu, menu);

        // Search button
        MenuItem btnFilter = menu.findItem(R.id.btn_filter_channel);
        SearchView searchView = (SearchView) btnFilter.getActionView();

        // Set search hint
        searchView.setQueryHint(getText(R.string.action_search_in_channel));

        // Filter on query text change
        rxSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        _fragment.getAdapter().getFilter().filter(event.queryText());
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onCreateOptionsMenu", "SearchViewQueryTextEvent", e);
                    }
                }));

        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onPrepareOptionsMenu(Menu menu) {
        super.onPrepareOptionsMenu(menu);

        boolean subscribed = getIntent().getBooleanExtra(ChannelActivity.EXTRA_SUBSCRIBED, false);
        MenuItem item = menu.findItem(R.id.btn_channel_favorite);
        // Toggle subscribed
        if (subscribed) {
            item.setIcon(R.drawable.ic_action_star);
            item.setTitle(R.string.action_unsubscribe);
        } else {
            item.setIcon(R.drawable.ic_action_star_outline);
            item.setTitle(R.string.action_subscribe);
        }

        return true;
    }

    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        if (TextUtils.isEmpty(action)) {
            return;
        }
        String dispersyCid = intent.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
        boolean subscribed = intent.getBooleanExtra(ChannelActivity.EXTRA_SUBSCRIBED, false);
        String title = intent.getStringExtra(Intent.EXTRA_TITLE);

        switch (action) {

            case Intent.ACTION_GET_CONTENT:
                // Set title
                ActionBar actionBar = getSupportActionBar();
                if (actionBar != null) {
                    if (!subscribed) {
                        title = getString(R.string.title_channel_preview) + ": " + title;
                    }
                    actionBar.setTitle(title);
                }
                return;

            case ACTION_TOGGLE_SUBSCRIBED:
                if (subscribed) {
                    _fragment.unsubscribe(dispersyCid, subscribed, title);
                } else {
                    _fragment.subscribe(dispersyCid, subscribed, title);
                }
                // Update view
                intent.putExtra(ChannelActivity.EXTRA_SUBSCRIBED, !subscribed);
                invalidateOptionsMenu();
                // Flag modification
                setResult(RESULT_FIRST_USER);
                return;
        }
    }

    public void btnFavoriteClicked(MenuItem item) {
        Intent intent = getIntent();
        intent.setAction(ACTION_TOGGLE_SUBSCRIBED);
        handleIntent(intent);
    }

}
