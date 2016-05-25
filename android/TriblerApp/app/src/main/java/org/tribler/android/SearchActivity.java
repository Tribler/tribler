package org.tribler.android;

import android.app.SearchManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.SearchView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;

import com.google.gson.Gson;

import java.util.ArrayList;
import java.util.List;

public class SearchActivity extends AppCompatActivity {

    private TriblerViewAdapter mAdapter;

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
            doMySearch(query);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar if it is present
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.activity_search_action_bar, menu);

        // Search button
        MenuItem btnSearch = (MenuItem) menu.findItem(R.id.btn_search);
        assert btnSearch != null;
        final SearchView searchView = (SearchView) btnSearch.getActionView();
        searchView.setIconifiedByDefault(false);
        searchView.requestFocus();

        SearchManager searchManager = (SearchManager) getSystemService(Context.SEARCH_SERVICE);
        searchView.setSearchableInfo(searchManager.getSearchableInfo(getComponentName()));

        searchView.setOnQueryTextListener(new SearchView.OnQueryTextListener() {
            /**
             * {@inheritDoc}
             */
            @Override
            public boolean onQueryTextSubmit(String query) {
                searchView.clearFocus();
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

    private void initGui() {
        setContentView(R.layout.activity_search);

        // Set list layout
        RecyclerView recyclerView = (RecyclerView) findViewById(R.id.search_results_list);
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