package org.tribler.android;

import android.app.Fragment;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.design.widget.Snackbar;
import android.support.v7.widget.RecyclerView;
import android.view.View;

import com.google.gson.stream.JsonReader;

import java.io.IOException;

import cz.msebera.android.httpclient.Header;

import static org.tribler.android.Triblerd.BASE_URL;
import static org.tribler.android.Triblerd.restApi;

public abstract class TriblerViewFragment extends Fragment implements TriblerViewAdapter.OnClickListener, TriblerViewAdapter.OnSwipeListener {

    protected TriblerViewAdapter mAdapter;
    private RecyclerView mRecyclerView;

    /**
     * {@inheritDoc}
     */
    @Nullable
    @Override
    public View getView() {
        return mRecyclerView;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mAdapter = new TriblerViewAdapter();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityCreated(Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);
        mRecyclerView = (RecyclerView) getActivity().findViewById(R.id.list_recycler_view);
        mAdapter.attachToRecyclerView(mRecyclerView);
        mAdapter.setOnClickListener(this);
        mAdapter.setOnSwipeListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        mRecyclerView = null;
        mAdapter.attachToRecyclerView(null);
        mAdapter.setOnClickListener(null);
        mAdapter.setOnSwipeListener(null);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerChannel channel) {
        //TODO: open channel
        Snackbar.make(getView(), "open channel", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerTorrent torrent) {
        //TODO: play video
        Snackbar.make(getView(), "play video", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        mAdapter.removeItem(channel);
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
                Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.msg_subscribe_success), Snackbar.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(int statusCode, Header[] headers, byte[] responseBody, Throwable error) {
                if (statusCode == 409) {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.msg_subscribe_already), Snackbar.LENGTH_LONG).show();
                } else {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.msg_subscribe_failure), Snackbar.LENGTH_LONG).show();
                }
            }

        });
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        mAdapter.removeItem(channel);
        restApi.delete(getActivity(), BASE_URL + "/channels/subscribed/" + channel.getDispersyCid(), null, new JsonStreamAsyncHttpResponseHandler() {
            /**
             * {@inheritDoc}
             */
            @Override
            protected void readJsonStream(JsonReader reader) throws IOException {
                reader.beginObject();
                if ("unsubscribed".equals(reader.nextName()) && reader.nextBoolean()) {
                    // unsubscribed: True
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
                Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.msg_unsubscribe_success), Snackbar.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(int statusCode, Header[] headers, byte[] responseBody, Throwable error) {
                if (statusCode == 404) {
                    //TODO:idea never see channel again?
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.msg_unsubscribe_already), Snackbar.LENGTH_LONG).show();
                } else {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.msg_unsubscribe_failure), Snackbar.LENGTH_LONG).show();
                }
            }

        });
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        //TODO: watch later
        Snackbar.make(getView(), "watch later", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        //TODO: not interested
        Snackbar.make(getView(), "not interested", Snackbar.LENGTH_LONG).show();

    }

}
