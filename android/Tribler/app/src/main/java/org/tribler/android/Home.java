package org.tribler.android;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;

import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;

import java.util.ArrayList;

public class Home extends AppCompatActivity {
    private ArrayList<AbstractContent> mTorrentList = new ArrayList<AbstractContent>();

    private RecyclerView mRecyclerView;
    private RecyclerView.Adapter mAdapter;
    private RecyclerView.LayoutManager mLayoutManager;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);
        mRecyclerView = (RecyclerView) findViewById(R.id.content_list);

        // use this setting to improve performance if you know that changes
        // in content do not change the layout size of the RecyclerView
        mRecyclerView.setHasFixedSize(true);

        // use a linear layout manager
        mLayoutManager = new LinearLayoutManager(this);
        mRecyclerView.setLayoutManager(mLayoutManager);

        // specify an adapter (see also next example)
        mAdapter = new ContentListViewAdapter(mTorrentList);
        mRecyclerView.setAdapter(mAdapter);

        fetchVideosData();
    }

    private ArrayList<TriblerTorrent> fetchVideosData() {
        TriblerTorrent torrentItem = new TriblerTorrent("Mad Max: Fury Road", "Action & Adventure", "2015");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Inside Out", "Animation, Kids & Family", "2015");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Star Wars: Episode VII - The Force Awakens", "Action", "2015");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Shaun the Sheep", "Animation", "2015");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("The Martian", "Science Fiction & Fantasy", "2015");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Mission: Impossible Rogue Nation", "Action", "2015");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Up", "Animation", "2009");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Star Trek", "Science Fiction", "2009");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("The LEGO Movie", "Animation", "2014");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Iron Man", "Action & Adventure", "2008");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Aliens", "Science Fiction", "1986");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Chicken Run", "Animation", "2000");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Back to the Future", "Science Fiction", "1985");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Raiders of the Lost Ark", "Action & Adventure", "1981");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Goldfinger", "Action & Adventure", "1965");
        mTorrentList.add(torrentItem);

        torrentItem = new TriblerTorrent("Guardians of the Galaxy", "Science Fiction & Fantasy", "2014");
        mTorrentList.add(torrentItem);

        mAdapter.notifyDataSetChanged();
    }
}