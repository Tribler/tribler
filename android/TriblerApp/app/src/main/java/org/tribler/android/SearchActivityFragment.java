package org.tribler.android;

import android.os.Message;
import android.support.design.widget.Snackbar;

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
    public void onClick(TriblerChannel channel) {
        //TODO: open channel
        Snackbar.make(getView(), "open channel", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(TriblerTorrent torrent) {
        //TODO: play video
        Snackbar.make(getView(), "play video", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(TriblerChannel channel) {
        //TODO: unsubscribe / not interested
        Snackbar.make(getView(), "unsubscribe", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        restApi.put(getActivity(), BASE_URL + "/channels/subscribed/" + channel.getDispersyCid(), null, new JsonStreamAsyncHttpResponseHandler() {
            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                if ("subscribed".equals(reader.nextName()) && reader.nextBoolean()) {
                    // subscribed: True
                } else {
                    return;
                }
                reader.endObject();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onSuccess(int statusCode, Header[] headers, byte[] responseBody) {
                Snackbar.make(getView(), getText(R.string.msg_subscribe_success) + channel.getName(), Snackbar.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(int statusCode, Header[] headers, byte[] responseBody, Throwable error) {
                if (statusCode == 409) {
                    Snackbar.make(getView(), getText(R.string.msg_subscribe_already) + channel.getName(), Snackbar.LENGTH_LONG).show();
                } else {
                    Snackbar.make(getView(), getText(R.string.msg_subscribe_failure) + channel.getName(), Snackbar.LENGTH_LONG).show();
                }
            }

        });
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(TriblerTorrent torrent) {
        //TODO: not interested
        Snackbar.make(getView(), "not interested", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(TriblerTorrent torrent) {
        //TODO: watch later
        Snackbar.make(getView(), "watch later", Snackbar.LENGTH_LONG).show();
    }

}
