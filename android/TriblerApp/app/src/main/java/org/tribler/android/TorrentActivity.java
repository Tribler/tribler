package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.view.Menu;

public class TorrentActivity extends BaseActivity {

    public static final String EXTRA_TORRENT_INFOHASH = "org.tribler.android.torrent.INFOHASH";
    public static final String EXTRA_NAME = "org.tribler.android.torrent.NAME";

    private TorrentFragment _fragment;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_torrent);

        _fragment = (TorrentFragment) getSupportFragmentManager().findFragmentById(R.id.fragment_torrent);
        _fragment.setRetainInstance(true);
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
    protected void handleIntent(Intent intent) {
        // TorrentFragment loads onCreate
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onPrepareOptionsMenu(Menu menu) {
        // Set title
        ActionBar actionBar = getSupportActionBar();
        if (actionBar != null) {
            actionBar.setTitle(getIntent().getStringExtra(EXTRA_NAME));
        }
        return super.onPrepareOptionsMenu(menu);
    }
}
