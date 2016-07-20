package org.tribler.android;

import android.app.Fragment;
import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.design.widget.Snackbar;
import android.support.v7.widget.RecyclerView;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import static org.tribler.android.RestApiClient.API;
import static org.tribler.android.RestApiClient.BASE_URL;
import static org.tribler.android.RestApiClient.TYPE_JSON;

public abstract class TriblerViewFragment extends Fragment implements TriblerViewAdapter.OnClickListener, TriblerViewAdapter.OnSwipeListener {

    protected TriblerViewAdapter mAdapter;
    private RecyclerView mRecyclerView;

    /**
     * {@inheritDoc}
     */
    @Nullable
    @Override
    public RecyclerView getView() {
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
        Intent intent = new Intent(getActivity(), ChannelActivity.class);
        intent.setAction(Intent.ACTION_GET_CONTENT);
        intent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, channel.getDispersyCid());
        intent.putExtra(Intent.EXTRA_TITLE, channel.getName());
        startActivity(intent);
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

        if (channel.isSubscribed()) {
            Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_subscribe_already), Snackbar.LENGTH_LONG).show();
            return;
        }

        Request request = new Request.Builder()
                .url(BASE_URL + "/channels/subscribed/" + channel.getDispersyCid())
                .put(RequestBody.create(TYPE_JSON, ""))
                .build();

        Callback callback = new Callback() {
            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(Call call, IOException e) {
                e.printStackTrace();
                Snackbar.make(getView(), e.getClass().getName(), Snackbar.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_subscribe_success), Snackbar.LENGTH_LONG).show();
                } else if (response.code() == 409) {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_subscribe_already), Snackbar.LENGTH_LONG).show();
                } else {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_subscribe_failure), Snackbar.LENGTH_LONG).show();
                }
            }
        };

        API.newCall(request).enqueue(callback);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        mAdapter.removeItem(channel);

        if (!channel.isSubscribed()) {
            //TODO: idea: never see channel again?
            Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_already), Snackbar.LENGTH_LONG).show();
            return;
        }

        Request request = new Request.Builder()
                .url(BASE_URL + "/channels/discovered")
                .delete()
                .build();

        Callback callback = new Callback() {
            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(Call call, IOException e) {
                e.printStackTrace();
                Snackbar.make(getView(), e.getClass().getName(), Snackbar.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_success), Snackbar.LENGTH_LONG).show();
                } else if (response.code() == 404) {
                    //TODO: idea: never see channel again?
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_already), Snackbar.LENGTH_LONG).show();
                } else {
                    Snackbar.make(getView(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_failure), Snackbar.LENGTH_LONG).show();
                }
            }
        };

        API.newCall(request).enqueue(callback);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        mAdapter.removeItem(torrent);
        //TODO: watch later
        Snackbar.make(getView(), "watch later", Snackbar.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        mAdapter.removeItem(torrent);
        //TODO: not interested
        //TODO: idea: never see torrent again?
        Snackbar.make(getView(), "not interested", Snackbar.LENGTH_LONG).show();

    }

}
