package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.Toast;

import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;
import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class DefaultInteractionListFragment extends ListFragment implements ListFragment.IListFragmentInteractionListener {

    protected IRestApi service;
    protected Context context;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        service = TriblerService.createService(baseUrl, authToken);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        service = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        this.context = context;
        setInteractionListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        context = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerChannel channel) {
        Intent intent = new Intent(context, ChannelActivity.class);
        intent.setAction(Intent.ACTION_GET_CONTENT);
        intent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, channel.getDispersyCid());
        intent.putExtra(Intent.EXTRA_TITLE, channel.getName());
        intent.putExtra(ChannelActivity.EXTRA_SUBSCRIBED, channel.isSubscribed());
        context.startActivity(intent);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerTorrent torrent) {
        //TODO: play video
        Toast.makeText(context, "play video", Toast.LENGTH_SHORT).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        adapter.removeObject(channel);

        if (channel.isSubscribed()) {
            Toast.makeText(context, channel.getName() + ' ' + context.getText(R.string.info_subscribe_already), Toast.LENGTH_SHORT).show();
            return;
        }

        rxSubs.add(service.subscribe(channel.getDispersyCid())
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SubscribedAck>() {

                    public void onNext(SubscribedAck response) {
                        Toast.makeText(context, channel.getName() + ' ' + context.getText(R.string.info_subscribe_success), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                            Toast.makeText(context, channel.getName() + ' ' + context.getText(R.string.info_subscribe_already), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("onSwipedRight", "subscribe", e);
                            // Retry
                            onSwipedRight(channel);
                        }
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        adapter.removeObject(channel);

        if (!channel.isSubscribed()) {
            Toast.makeText(context, channel.getName() + ' ' + context.getText(R.string.info_unsubscribe_already), Toast.LENGTH_SHORT).show();
            return;
        }

        rxSubs.add(service.unsubscribe(channel.getDispersyCid())
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<UnsubscribedAck>() {

                    public void onNext(UnsubscribedAck response) {
                        Toast.makeText(context, channel.getName() + ' ' + context.getText(R.string.info_unsubscribe_success), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            Toast.makeText(context, channel.getName() + ' ' + context.getText(R.string.info_unsubscribe_already), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("onSwipedLeft", "unsubscribe", e);
                            // Retry
                            onSwipedLeft(channel);
                        }
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        adapter.removeObject(torrent);

        switch (torrent.getCategory()) {
            case "Video":
                //TODO: watch later
                Toast.makeText(context, "watch later", Toast.LENGTH_SHORT).show();
                break;

            case "Audio":
                //TODO: listen later
                Toast.makeText(context, "listen later", Toast.LENGTH_SHORT).show();
                break;

            case "Document":
                //TODO: read later
                Toast.makeText(context, "listen later", Toast.LENGTH_SHORT).show();
                break;

            case "Compressed":
            case "xxx":
            case "other":
                //TODO: download
                Toast.makeText(context, "download", Toast.LENGTH_SHORT).show();
                break;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        adapter.removeObject(torrent);

        //TODO: not interested never see again
    }

}
