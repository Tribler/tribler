package org.tribler.android;

import android.os.Message;
import android.support.design.widget.Snackbar;
import android.view.View;

import com.google.gson.stream.JsonReader;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.BASE_URL;
import static org.tribler.android.Triblerd.restApi;

public class SearchActivityFragment extends TriblerViewFragment {

    public void doMySearch(String query) {
        mAdapter.clear();
        //TODO: real search
        restApi.get(getActivity(), BASE_URL + "/channels/discovered", new JsonStreamAsyncHttpResponseHandler() {
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

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(View view, TriblerChannel channel) {
        //TODO: open channel
        Snackbar.make(view, "open channel", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(View view, TriblerTorrent torrent) {
        //TODO: play video
        Snackbar.make(view, "play video", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(View view, TriblerChannel channel) {
        //TODO: unsubscribe / not interested
        Snackbar.make(view, "unsubscribe", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(View view, TriblerChannel channel) {
        //TODO: subscribe / favorite
        Snackbar.make(view, "subscribe", Snackbar.LENGTH_LONG).show();

        restApi.put(getActivity(), BASE_URL + "/channels/subscribed/" + channel.getDispersyCid(), null, new JsonStreamAsyncHttpResponseHandler() {
            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                
                reader.endObject();
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
                // Ignore error 409 if already subscribed to this channel
            }

        });
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(View view, TriblerTorrent torrent) {
        //TODO: not interested
        Snackbar.make(view, "not interested", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(View view, TriblerTorrent torrent) {
        //TODO: watch later
        Snackbar.make(view, "watch later", Snackbar.LENGTH_LONG).show();
    }

}
