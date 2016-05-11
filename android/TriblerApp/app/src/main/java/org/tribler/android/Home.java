package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;

import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.support.v7.widget.SearchView;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.MotionEvent;
import android.view.View;

import com.google.gson.Gson;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class Home extends AppCompatActivity {

    private TriblerViewAdapter mAdapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        //ServiceTriblerd.start(this, "");

        initGui();
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
    public boolean onCreateOptionsMenu(final Menu menu) {
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.action_menu, menu);

        // Camera button
        final MenuItem btn_camera = (MenuItem) menu.findItem(R.id.btn_camera);
        btn_camera.setOnMenuItemClickListener(
                new MenuItem.OnMenuItemClickListener() {
                    @Override
                    public boolean onMenuItemClick(MenuItem menuItem) {
                        //TODO
                        return false;
                    }
                }
        );

        // Search button
        final MenuItem btn_search = (MenuItem) menu.findItem(R.id.btn_search);
        final SearchView searchView = (SearchView) btn_search.getActionView();
        SearchManager searchManager = (SearchManager) getSystemService(Context.SEARCH_SERVICE);
        searchView.setSearchableInfo(searchManager.getSearchableInfo(getComponentName()));
        searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
            @Override
            public boolean onQueryTextSubmit(String query) {
                searchView.clearFocus();
                doMySearch(query);
                return true;
            }

            @Override
            public boolean onQueryTextChange(String newText) {
                return false;
            }
        });
        searchView.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
            @Override
            public void onViewAttachedToWindow(View view) {
                btn_camera.setVisible(false);
            }

            @Override
            public void onViewDetachedFromWindow(View view) {
                btn_camera.setVisible(true);
            }
        });

        return true;
    }

    private void doMySearch(String query) {
        mAdapter.getList().clear();
        mAdapter.notifyDataSetChanged();
        //TODO
        exampleData();
    }

    private void initGui() {
        setContentView(R.layout.activity_home);

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
        TriblerViewClickListener.OnItemClickListener onClick = new HomeClickCallback(mAdapter);
        RecyclerView.SimpleOnItemTouchListener touchListener = new TriblerViewClickListener(this, onClick);
        recyclerView.addOnItemTouchListener(touchListener);

        // Swipe list item
        ItemTouchHelper.SimpleCallback onSwipe = new HomeSwipeCallback(mAdapter);
        ItemTouchHelper touchHelper = new ItemTouchHelper(onSwipe);
        touchHelper.attachToRecyclerView(recyclerView);
    }

    private void initBeam() {
        // Send app apk with Android Beam from this activity
        File apk = new File(this.getPackageResourcePath());
        MyBeamCallback beam = new MyBeamCallback(this);
        beam.addFile(apk);
    }

    private void exampleData() {
        Gson gson = new Gson();
        List<Object> list = mAdapter.getList();

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

        mAdapter.notifyDataSetChanged();
    }

}