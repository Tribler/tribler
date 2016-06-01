package org.tribler.android;

import android.app.Fragment;
import android.os.Bundle;
import android.os.Message;
import android.support.design.widget.Snackbar;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;
import android.view.View;

import com.google.gson.stream.JsonReader;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.restApi;

public class SearchActivityFragment extends Fragment implements TriblerViewAdapter.OnClickListener {

    private TriblerViewAdapter mAdapter;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mAdapter = new TriblerViewAdapter(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityCreated(Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);

        RecyclerView recyclerView = (RecyclerView) getActivity().findViewById(R.id.search_results_list);
        recyclerView.setAdapter(mAdapter);

        // Swipe list item
        ItemTouchHelper.SimpleCallback onSwipe = new TriblerViewAdapterSwipeListener(mAdapter);
        ItemTouchHelper touchHelper = new ItemTouchHelper(onSwipe);
        touchHelper.attachToRecyclerView(recyclerView);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(View view, TriblerChannel channel) {
        //TODO: open channel
        Snackbar.make(view, channel.getDescription(), Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(View view, TriblerTorrent torrent) {
        //TODO: play video
        Snackbar.make(view, torrent.getTitle(), Snackbar.LENGTH_LONG).show();
    }

    public void doMySearch(String query) {
        mAdapter.clear();
        //TODO: real search
        restApi.get(getActivity(), Triblerd.BASE_URL + "/channels/discovered", new JsonStreamAsyncHttpResponseHandler() {
            private static final int CHANNEL = 100;
            private static final int TORRENT = 200;

            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                reader.nextName(); // "channels":
                reader.beginArray();
                while (reader.hasNext()) {
                    TriblerChannel channel = gson.fromJson(reader, TriblerChannel.class);
                    Message msg = obtainMessage(CHANNEL, channel);
                    sendMessage(msg);
                }
                reader.endArray();
                reader.endObject();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void handleMessage(Message message) {
                switch (message.what) {

                    case CHANNEL:
                    case TORRENT:
                        mAdapter.addItem(message.obj);
                        break;

                    default:
                        super.handleMessage(message);
                }
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onSuccess(int statusCode, Header[] headers, byte[] responseBody) {
                //nothing
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(int statusCode, Header[] headers, byte[] responseBody, Throwable error) {
                //TODO: advise user
            }
        });
    }

}
