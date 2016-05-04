package org.tribler.android;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;

import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.view.MotionEvent;

import com.google.gson.Gson;

import java.util.ArrayList;

public class Home extends AppCompatActivity {
    private ArrayList<Object> mList;
    private MyViewAdapter mAdapter;

    private ItemTouchHelper.SimpleCallback mItemSwipeCallback =
            new ItemTouchHelper.SimpleCallback(0, ItemTouchHelper.LEFT | ItemTouchHelper.RIGHT) {
                @Override
                public void onSwiped(RecyclerView.ViewHolder viewHolder, int swipeDir) {
                    int position = viewHolder.getAdapterPosition();
                    // Swipe channel
                    if (viewHolder instanceof MyViewAdapter.ChannelViewHolder) {
                        TriblerChannel channel = (TriblerChannel) mAdapter.getItem(position);
                        if (swipeDir == ItemTouchHelper.LEFT) {
                            // un-subscribe / not interested
                        } else if (swipeDir == ItemTouchHelper.RIGHT) {
                            // subscribe / favorite
                        }
                    }
                    // Swipe torrent
                    else if (viewHolder instanceof MyViewAdapter.TorrentViewHolder) {
                        TriblerTorrent torrent = (TriblerTorrent) mAdapter.getItem(position);
                        if (swipeDir == ItemTouchHelper.LEFT) {
                            // not interested
                        } else if (swipeDir == ItemTouchHelper.RIGHT) {
                            // watch later
                        }
                    }
                }

                @Override
                /**
                 * Not draggable
                 */
                public boolean isLongPressDragEnabled() {
                    return false;
                }

                @Override
                /**
                 * Not draggable
                 */
                public boolean onMove(RecyclerView recyclerView, RecyclerView.ViewHolder viewHolder,
                                      RecyclerView.ViewHolder target) {
                    return false;
                }
            };


    private RecyclerView.OnItemTouchListener mItemTouchListener = new RecyclerView.SimpleOnItemTouchListener() {
        @Override
        public void onTouchEvent(RecyclerView rv, MotionEvent e) {

        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        RecyclerView mRecyclerView = (RecyclerView) findViewById(R.id.content_list);
        // Improve performance since change in content does not change the layout size
        mRecyclerView.setHasFixedSize(true);

        RecyclerView.LayoutManager mLayoutManager = new LinearLayoutManager(this);
        mRecyclerView.setLayoutManager(mLayoutManager);

        mList = new ArrayList<Object>();

        mAdapter = new MyViewAdapter(mList);
        mRecyclerView.setAdapter(mAdapter);

        ItemTouchHelper mItemTouchHelper = new ItemTouchHelper(mItemSwipeCallback);
        mItemTouchHelper.attachToRecyclerView(mRecyclerView);

        Gson gson = new Gson();

        mList.add(gson.fromJson("{title:'Mad Max: Fury Road', genre:'Action & Adventure', year:2015}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Inside Out', genre:'Animation, Kids & Family', year:2015}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Star Wars: Episode VII - The Force Awakens', genre:'Action', year:2015}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Shaun the Sheep', genre:'Animation', year:2015}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'The Martian', genre:'Science Fiction & Fantasy', year:2015}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Mission: Impossible Rogue Nation', genre:'Action', year:2015}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Up', genre:'Animation', year:2009}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Star Trek', genre:'Science Fiction', year:2009}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'The LEGO Movie', genre:'Animation', year:2014}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Iron Man', genre:'Action & Adventure', year:2008}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Aliens', genre:'Science Fiction', year:1986}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Chicken Run', genre:'Animation', year:2000}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Back to the Future', genre:'Science Fiction', year:1985}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Raiders of the Lost Ark', genre:'Action & Adventure', year:1981}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Goldfinger', genre:'Action & Adventure', year:1965}", TriblerTorrent.class));
        mList.add(gson.fromJson("{title:'Guardians of the Galaxy', genre:'Science Fiction & Fantasy', year:2014}", TriblerTorrent.class));

        mAdapter.notifyDataSetChanged();
    }

}