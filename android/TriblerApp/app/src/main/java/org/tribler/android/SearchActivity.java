package org.tribler.android;

import android.os.Bundle;
import android.content.Intent;
import android.app.SearchManager;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

import java.util.ArrayList;
import java.util.List;

public class SearchActivity extends AppCompatActivity {

    private TriblerViewAdapter mAdapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        initGui();

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

    private void initGui() {
        setContentView(R.layout.activity_search);

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


    private void doMySearch(String query) {
        //TODO
        List<Object> results = new ArrayList<Object>();
        mAdapter.setList(results);
        mAdapter.notifyDataSetChanged();
    }

}