package org.tribler.android;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;

import android.support.v7.widget.DefaultItemAnimator;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.Toolbar;

import java.util.ArrayList;
import java.util.List;

public class Home extends AppCompatActivity {
    private List<Video> videoList = new ArrayList<>();
    private RecyclerView recyclerView;
    private VideosViewAdapter mAdapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);
//        Toolbar toolbar = (Toolbar) findViewById(R.id.toolbar);
//        setSupportActionBar(toolbar);

        recyclerView = (RecyclerView) findViewById(R.id.content_list);

        mAdapter = new VideosViewAdapter(videoList);
        RecyclerView.LayoutManager mLayoutManager = new LinearLayoutManager(getApplicationContext());
        recyclerView.setLayoutManager(mLayoutManager);
        recyclerView.setItemAnimator(new DefaultItemAnimator());
        recyclerView.setAdapter(mAdapter);

        prepareMovieData();
    }

    private void prepareMovieData() {
        Video video = new Video("Mad Max: Fury Road", "Action & Adventure", "2015");
        videoList.add(video);

        video = new Video("Inside Out", "Animation, Kids & Family", "2015");
        videoList.add(video);

        video = new Video("Star Wars: Episode VII - The Force Awakens", "Action", "2015");
        videoList.add(video);

        video = new Video("Shaun the Sheep", "Animation", "2015");
        videoList.add(video);

        video = new Video("The Martian", "Science Fiction & Fantasy", "2015");
        videoList.add(video);

        video = new Video("Mission: Impossible Rogue Nation", "Action", "2015");
        videoList.add(video);

        video = new Video("Up", "Animation", "2009");
        videoList.add(video);

        video = new Video("Star Trek", "Science Fiction", "2009");
        videoList.add(video);

        video = new Video("The LEGO Movie", "Animation", "2014");
        videoList.add(video);

        video = new Video("Iron Man", "Action & Adventure", "2008");
        videoList.add(video);

        video = new Video("Aliens", "Science Fiction", "1986");
        videoList.add(video);

        video = new Video("Chicken Run", "Animation", "2000");
        videoList.add(video);

        video = new Video("Back to the Future", "Science Fiction", "1985");
        videoList.add(video);

        video = new Video("Raiders of the Lost Ark", "Action & Adventure", "1981");
        videoList.add(video);

        video = new Video("Goldfinger", "Action & Adventure", "1965");
        videoList.add(video);

        video = new Video("Guardians of the Galaxy", "Science Fiction & Fantasy", "2014");
        videoList.add(video);

        mAdapter.notifyDataSetChanged();
    }
}