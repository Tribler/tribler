package org.tribler.android;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;

import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

import java.nio.channels.Channel;
import java.util.ArrayList;

public class Home extends AppCompatActivity {
    private ArrayList<Object> mList = new ArrayList<Object>();

    private RecyclerView mRecyclerView;
    private MyViewAdapter mAdapter;
    private RecyclerView.LayoutManager mLayoutManager;

    private ItemTouchHelper.SimpleCallback mItemTouchCallback =
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
                public boolean onMove(RecyclerView recyclerView, RecyclerView.ViewHolder viewHolder,
                                      RecyclerView.ViewHolder target) {
                    return false;
                }
            };

    private ItemTouchHelper mItemTouchHelper = new ItemTouchHelper(mItemTouchCallback);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);
        mRecyclerView = (RecyclerView) findViewById(R.id.content_list);

        // use this setting to improve performance if you know that changes
        // in content do not change the layout size of the RecyclerView
        mRecyclerView.setHasFixedSize(true);

        mLayoutManager = new LinearLayoutManager(this);
        mRecyclerView.setLayoutManager(mLayoutManager);

        mAdapter = new MyViewAdapter(mList);
        mRecyclerView.setAdapter(mAdapter);

        mItemTouchHelper.attachToRecyclerView(mRecyclerView);
    }

}