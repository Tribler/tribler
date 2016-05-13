package org.tribler.android;

import android.app.SearchManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;

import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.support.v7.widget.SearchView;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;

import com.google.gson.Gson;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class Home extends AppCompatActivity {
    public static final int CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE = 200;

    private TriblerViewAdapter mAdapter;
    private SearchViewListener mSearchViewListener;
    private CaptureVideoListener mCaptureVideoListener;
    private NfcBeamListener mNfcBeamListener;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        ServiceTriblerd.start(this, "");

        initGui();
        initSearch();
        initCaptureVideo();
        initBeam();

        handleIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (Intent.ACTION_SEARCH.equals(intent.getAction())) {
            String query = intent.getStringExtra(SearchManager.QUERY);
            doMySearch(query);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == CAPTURE_VIDEO_ACTIVITY_REQUEST_CODE) {
            mCaptureVideoListener.onActivityResult(resultCode, data);
        }
    }

    @Override
    public boolean onCreateOptionsMenu(final Menu menu) {
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.action_menu, menu);

        // Upload button
        final MenuItem btnUpload = (MenuItem) menu.findItem(R.id.btn_upload);
        btnUpload.setOnMenuItemClickListener(new MenuItem.OnMenuItemClickListener() {
            @Override
            public boolean onMenuItemClick(MenuItem menuItem) {
                //TODO
                return false;
            }
        });

        // Record button
        final MenuItem btnRecord = (MenuItem) menu.findItem(R.id.btn_record);
        // Check if device has camera
        if (mCaptureVideoListener != null) {
            btnRecord.setOnMenuItemClickListener(mCaptureVideoListener);
        } else {
            btnRecord.setEnabled(false).setVisible(false);
        }

        // Search button
        final MenuItem btnSearch = (MenuItem) menu.findItem(R.id.btn_search);
        SearchView searchView = (SearchView) btnSearch.getActionView();
        mSearchViewListener.setSearchView(searchView);
        searchView.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
            private List<Object> mPrevList;

            @Override
            public void onViewAttachedToWindow(View view) {
                // Hide other buttons
                btnUpload.setVisible(false);
                btnRecord.setVisible(false);

                // Stash current list
                mPrevList = mAdapter.getList();
                mAdapter.setList(new ArrayList<Object>());
                // Notify adapter after first search result arrived
            }

            @Override
            public void onViewDetachedFromWindow(View view) {
                // Show other buttons
                btnUpload.setVisible(btnUpload.isEnabled());
                btnRecord.setVisible(btnRecord.isEnabled());

                // Drop search results
                mAdapter.setList(mPrevList);
                mAdapter.notifyDataSetChanged();
            }
        });

        return true;
    }

    private void initGui() {
        // Set list layout
        RecyclerView recyclerView = (RecyclerView) findViewById(R.id.content_list);
        recyclerView.setHasFixedSize(true);
        RecyclerView.LayoutManager layoutManager = new LinearLayoutManager(this);
        recyclerView.setLayoutManager(layoutManager);

        // Set list adapter
        List<Object> list = new ArrayList<Object>();
        mAdapter = new TriblerViewAdapter(list);
        recyclerView.setAdapter(mAdapter);

        // Click list item
        TriblerViewClickListener.OnItemClickListener onClick = new HomeClickListener(mAdapter);
        RecyclerView.SimpleOnItemTouchListener touchListener = new TriblerViewClickListener(this, onClick);
        recyclerView.addOnItemTouchListener(touchListener);

        // Swipe list item
        ItemTouchHelper.SimpleCallback onSwipe = new HomeSwipeListener(mAdapter);
        ItemTouchHelper touchHelper = new ItemTouchHelper(onSwipe);
        touchHelper.attachToRecyclerView(recyclerView);
    }

    private void initSearch() {
        mSearchViewListener = new SearchViewListener(this);
    }

    private void initCaptureVideo() {
        // Check if device has camera
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA)) {
            mCaptureVideoListener = new CaptureVideoListener(this);
        }
    }

    private void initBeam() {
        // Check if device has nfc
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            mNfcBeamListener = new NfcBeamListener(this);
            // Send app apk with Android Beam from this activity
            File apk = new File(this.getPackageResourcePath());
            mNfcBeamListener.addFile(apk);
        }
    }

    private void doMySearch(String query) {
        //TODO
        List<Object> results = exampleData();
        mAdapter.setList(results);
        mAdapter.notifyDataSetChanged();
    }

    private List<Object> exampleData() {
        Gson gson = new Gson();
        List<Object> list = new ArrayList<Object>();

        list.add(gson.fromJson("{title:'Mad Max: Fury Road', genre:'Action & Adventure', year:2015}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Inside Out', genre:'Animation, Kids & Family', year:2015}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Star Wars: Episode VII - The Force Awakens', genre:'Action', year:2015}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Shaun the Sheep', genre:'Animation', year:2015}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'The Martian', genre:'Science Fiction & Fantasy', year:2015}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Mission: Impossible Rogue Nation', genre:'Action', year:2015}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Up', genre:'Animation', year:2009}", TriblerTorrent.class));
        list.add(gson.fromJson("{name:'Debian', commentsCount:123456, torrentsCount:8}", TriblerChannel.class));
        list.add(gson.fromJson("{name:'Red Hat', commentsCount:987654, torrentsCount:200}", TriblerChannel.class));
        list.add(gson.fromJson("{title:'Star Trek', genre:'Science Fiction', year:2009}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'The LEGO Movie', genre:'Animation', year:2014}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Iron Man', genre:'Action & Adventure', year:2008}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Aliens', genre:'Science Fiction', year:1986}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Chicken Run', genre:'Animation', year:2000}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Back to the Future', genre:'Science Fiction', year:1985}", TriblerTorrent.class));
        list.add(gson.fromJson("{name:'Pioneer One', commentsCount:0, torrentsCount:36}", TriblerChannel.class));
        list.add(gson.fromJson("{title:'Raiders of the Lost Ark', genre:'Action & Adventure', year:1981}", TriblerTorrent.class));
        list.add(gson.fromJson("{title:'Goldfinger', genre:'Action & Adventure', year:1965}", TriblerTorrent.class));
        list.add(gson.fromJson("{name:'Ubuntu', commentsCount:132, torrentsCount:16}", TriblerChannel.class));
        list.add(gson.fromJson("{title:'Guardians of the Galaxy', genre:'Science Fiction & Fantasy', year:2014}", TriblerTorrent.class));
        list.add(gson.fromJson("{name:'Fedora', commentsCount:999, torrentsCount:8}", TriblerChannel.class));

        return list;
    }

}