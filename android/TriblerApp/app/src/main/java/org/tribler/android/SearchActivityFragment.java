package org.tribler.android;

import android.app.Fragment;
import android.os.Bundle;
import android.os.Message;
import android.support.v7.widget.RecyclerView;
import android.support.v7.widget.helper.ItemTouchHelper;

import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;
import com.loopj.android.http.AsyncHttpResponseHandler;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;

import cz.msebera.android.httpclient.Header;
import cz.msebera.android.httpclient.HttpEntity;
import cz.msebera.android.httpclient.HttpResponse;

public class SearchActivityFragment extends Fragment {

    private TriblerViewAdapter mAdapter;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Tell the framework to try to keep this fragment around during a configuration change
        setRetainInstance(true);

        mAdapter = new TriblerViewAdapter();
    }

    @Override
    public void onActivityCreated(Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);

        RecyclerView recyclerView = (RecyclerView) getActivity().findViewById(R.id.search_results_list);
        // Set list adapter
        recyclerView.setAdapter(mAdapter);

        // Click list item
        TriblerViewClickListener.OnItemClickListener onClick = new HomeClickListener(mAdapter);
        RecyclerView.SimpleOnItemTouchListener touchListener = new TriblerViewClickListener(getActivity(), onClick);
        recyclerView.addOnItemTouchListener(touchListener);

        // Swipe list item
        ItemTouchHelper.SimpleCallback onSwipe = new HomeSwipeListener(mAdapter);
        ItemTouchHelper touchHelper = new ItemTouchHelper(onSwipe);
        touchHelper.attachToRecyclerView(recyclerView);
    }

    public void doMySearch(String query) {
        //TODO
        Triblerd.restApi.get(getActivity(), Triblerd.BASE_URL + "/channels/discovered", new AsyncHttpResponseHandler() {

            protected static final int MY_MESSAGE = -1;

            public Gson gson = new Gson();

            /**
             * {@inheritDoc}
             */
            @Override
            public void sendResponseMessage(HttpResponse response) throws IOException {
                // do not process if request has been cancelled
                if (!Thread.currentThread().isInterrupted()) {
                    HttpEntity entity = response.getEntity();
                    if (entity != null) {
                        InputStream inputStream = entity.getContent();
                        if (inputStream != null) {
                            readJsonStream(inputStream);
                        }
                    }
                }
            }

            /**
             * This code reads a JSON document containing an array of messages.
             * It steps through array elements as a stream to avoid loading the complete document into memory.
             * It is concise because it uses Gson’s object-model to parse the individual messages:
             *
             * @param in
             * @return
             * @throws IOException
             */
            public void readJsonStream(InputStream in) throws IOException {
                JsonReader reader = new JsonReader(new InputStreamReader(in, getCharset()));
                reader.beginObject();
                reader.nextName(); // "channels":
                reader.beginArray();
                while (reader.hasNext()) {
                    TriblerChannel channel = gson.fromJson(reader, TriblerChannel.class);
                    sendMyMessage(channel);
                }
                reader.endArray();
                reader.endObject();
                reader.close();
            }

            final public void sendMyMessage(TriblerChannel channel) {
                sendMessage(obtainMessage(MY_MESSAGE, channel));
            }

            @Override
            protected void handleMessage(Message message) {
                if (MY_MESSAGE == message.what) {
                    onMy((TriblerChannel) message.obj);
                } else {
                    super.handleMessage(message);
                }
            }

            public void onMy(TriblerChannel channel) {
                mAdapter.addItem(channel);
            }

            @Override
            public void onSuccess(int statusCode, Header[] headers, byte[] responseBody) {
                // unused
            }

            @Override
            public void onFailure(int statusCode, Header[] headers, byte[] responseBody, Throwable error) {
                // unused
            }
        });
    }

}
