package org.tribler.android;

import android.content.Intent;
import android.widget.Toast;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import static org.tribler.android.RestApiClient.API;
import static org.tribler.android.RestApiClient.BASE_URL;
import static org.tribler.android.RestApiClient.TYPE_JSON;

public class DefaultInteractionListFragment extends ListFragment implements ListFragment.IListFragmentInteractionListener {

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
        Toast.makeText(getActivity(), "play video", Toast.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        mAdapter.removeObject(channel);

        if (channel.isSubscribed()) {
            Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_subscribe_already), Toast.LENGTH_LONG).show();
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
                Toast.makeText(getActivity(), e.getClass().getName(), Toast.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_subscribe_success), Toast.LENGTH_LONG).show();
                } else if (response.code() == 409) {
                    Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_subscribe_already), Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_subscribe_failure), Toast.LENGTH_LONG).show();
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
        mAdapter.removeObject(channel);

        if (!channel.isSubscribed()) {
            //TODO: idea: never see channel again?
            Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_already), Toast.LENGTH_LONG).show();
            return;
        }

        Request request = new Request.Builder()
                .url(BASE_URL + "/channels/subscribed")
                .delete()
                .build();

        Callback callback = new Callback() {
            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(Call call, IOException e) {
                e.printStackTrace();
                Toast.makeText(getActivity(), e.getClass().getName(), Toast.LENGTH_LONG).show();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_success), Toast.LENGTH_LONG).show();
                } else if (response.code() == 404) {
                    //TODO: idea: never see channel again?
                    Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_already), Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(getActivity(), channel.getName() + ' ' + getText(R.string.info_unsubscribe_failure), Toast.LENGTH_LONG).show();
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
        mAdapter.removeObject(torrent);
        //TODO: watch later
        Toast.makeText(getActivity(), "watch later", Toast.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        mAdapter.removeObject(torrent);
        //TODO: not interested
        //TODO: idea: never see torrent again?
        Toast.makeText(getActivity(), "not interested", Toast.LENGTH_LONG).show();

    }

}
