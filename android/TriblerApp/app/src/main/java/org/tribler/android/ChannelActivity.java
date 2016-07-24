package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.Toolbar;
import android.view.Menu;
import android.view.MenuItem;

import butterknife.BindView;

public class ChannelActivity extends BaseActivity {

    public static final String EXTRA_DISPERSY_CID = "dispersy.CID";

    @BindView(R.id.toolbar)
    Toolbar toolbar;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_channel);

        // The action bar will automatically handle clicks on the Home/Up button,
        // so long as you specify a parent activity in AndroidManifest.xml
        setSupportActionBar(toolbar);
        ActionBar actionbar = getSupportActionBar();
        if (actionbar != null) {
            actionbar.setDisplayHomeAsUpEnabled(true);
        }

        handleIntent(getIntent());
    }

    protected void handleIntent(Intent intent) {
        if (Intent.ACTION_GET_CONTENT.equals(intent.getAction())) {
            String cid = intent.getStringExtra(EXTRA_DISPERSY_CID);

            // Get torrents for channel
            ChannelFragment channelFragment = (ChannelFragment)
                    getFragmentManager().findFragmentById(R.id.fragment_channel);
            channelFragment.getTorrents(cid);

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
        MenuItem btnSearch = menu.findItem(R.id.btn_search);
        SearchView searchView = (SearchView) btnSearch.getActionView();
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
                ChannelFragment channelFragment = (ChannelFragment)
                        getFragmentManager().findFragmentById(R.id.fragment_channel);
                channelFragment.adapter.getFilter().filter(query);
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
        // Close search if open
        SearchView searchView = (SearchView) findViewById(R.id.btn_search);
        if (!searchView.isIconified()) {
            searchView.setIconified(true);
        } else {
            super.onBackPressed();
        }
    }
}
