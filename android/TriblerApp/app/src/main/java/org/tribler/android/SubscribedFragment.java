package org.tribler.android;

import android.os.Message;

import com.google.gson.stream.JsonReader;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.BASE_URL;
import static org.tribler.android.Triblerd.restApi;

public class SubscribedFragment extends TriblerViewFragment {
    public static final String TAG = SubscribedFragment.class.getSimpleName();

    public void getSubscriptions() {
        restApi.get(getActivity(), BASE_URL + "/channels/subscribed", new JsonStreamAsyncHttpResponseHandler() {
            private static final int CHANNEL = 100;

            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                if ("subscribed".equals(reader.nextName())) {
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
            public void onFailure(int statusCode, Header[] headers,
                                  byte[] responseBody, Throwable error) {
                //TODO: advise user
            }
        });
    }

}
