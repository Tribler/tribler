package org.tribler.android;

import android.app.Fragment;
import android.os.Bundle;
import android.os.Message;
import android.support.v7.widget.RecyclerView;

import com.google.gson.stream.JsonReader;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.restApi;

public class SearchActivityFragment extends Fragment {

    private TriblerViewAdapter mAdapter;
    private TriblerViewAdapterSwipeListener mSwipeListener;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mAdapter = new TriblerViewAdapter();
        mSwipeListener = new TriblerViewAdapterSwipeListener(mAdapter);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityCreated(Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);
        RecyclerView recyclerView = (RecyclerView) getActivity().findViewById(R.id.search_results_list);
        recyclerView.setAdapter(mAdapter);
        mAdapter.setOnClickListener((TriblerViewAdapter.OnClickListener) getActivity());
        mAdapter.setOnSwipeListener((TriblerViewAdapter.OnSwipeListener) getActivity());
        mSwipeListener.attachToRecyclerView(recyclerView);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        mSwipeListener.attachToRecyclerView(null);
        mAdapter.setOnClickListener(null);
        mAdapter.setOnSwipeListener(null);
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
