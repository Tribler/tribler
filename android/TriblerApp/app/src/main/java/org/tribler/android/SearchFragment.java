package org.tribler.android;

import android.os.Message;

import com.google.gson.stream.JsonReader;
import com.loopj.android.http.RequestHandle;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.BASE_URL;
import static org.tribler.android.Triblerd.restApi;

public class SearchFragment extends TriblerViewFragment {
    public static final String TAG = SearchFragment.class.getSimpleName();

    private RequestHandle mSearchRequest;

    public void startSearch(String query) {
        if (mSearchRequest != null) {
            mSearchRequest.cancel(true);
            mAdapter.clear();
        }
        //TODO: real search
        mSearchRequest = restApi.get(getActivity(), BASE_URL + "/channels/discovered", new JsonStreamAsyncHttpResponseHandler() {
            private static final int CHANNEL = 100;
            private static final int TORRENT = 200;

            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                if ("channels".equals(reader.nextName())) {
                    reader.beginArray();
                    while (reader.hasNext()) {
                        TriblerChannel channel = gson.fromJson(reader, TriblerChannel.class);
                        Message msg = obtainMessage(CHANNEL, channel);
                        sendMessage(msg);
                    }
                    reader.endArray();
                } else {
                    return;
                }
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
                // Nothing
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
