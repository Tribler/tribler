package org.tribler.android;

import android.os.Message;

import com.google.gson.stream.JsonReader;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.BASE_URL;
import static org.tribler.android.Triblerd.restApi;

public class ChannelFragment extends TriblerViewFragment {
    public static final String TAG = ChannelFragment.class.getSimpleName();

    public void getTorrents(String dispersyCid) {
        restApi.get(getActivity(), BASE_URL + "/channels/discovered/" + dispersyCid + "/torrents", new JsonStreamAsyncHttpResponseHandler() {
            private static final int TORRENT = 200;

            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                if ("torrents".equals(reader.nextName())) {
                    reader.beginArray();
                    while (reader.hasNext()) {
                        TriblerTorrent torrent = gson.fromJson(reader, TriblerTorrent.class);
                        Message msg = obtainMessage(TORRENT, torrent);
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
            public void onFailure(int statusCode, Header[] headers,
                                  byte[] responseBody, Throwable error) {
                //TODO: advise user
            }
        });
    }

}