package org.tribler.android;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import android.view.View;
import android.widget.Toast;

import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import java.util.concurrent.TimeUnit;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.exceptions.Exceptions;
import rx.schedulers.Schedulers;

public class DefaultInteractionListFragment extends ListFragment implements ListFragment.IListFragmentInteractionListener {

    public static final int CHANNEL_ACTIVITY_REQUEST_CODE = 301;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        setListInteractionListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerChannel channel) {
        Intent intent = MyUtils.viewChannelIntent(channel.getDispersyCid(), channel.getName(), channel.isSubscribed());
        startActivityForResult(intent, CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        switch (requestCode) {

            case CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_FIRST_USER:
                        // Update the subscription status of the channel identified by dispersy_cid
                        String dispersyCid = data.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
                        boolean subscribed = data.getBooleanExtra(ChannelActivity.EXTRA_SUBSCRIBED, false);

                        TriblerChannel channel = adapter.findByDispersyCid(dispersyCid);
                        if (channel != null) {
                            channel.setSubscribed(subscribed);
                            // Update view
                            adapter.notifyObjectChanged(channel);
                        }
                        return;
                }
                return;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        adapter.removeObject(channel);
        subscribe(channel.getDispersyCid(), channel.isSubscribed(), channel.getName());
    }

    void subscribe(final String dispersyCid, final boolean subscribed, final String name) {
        if (subscribed) {
            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_already), name), Toast.LENGTH_SHORT).show();
            return;
        }

        rxSubs.add(service.subscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .doOnError(e -> {
                    if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_already), name), Toast.LENGTH_SHORT).show();
                    } else {
                        throw Exceptions.propagate(e);
                    }
                })
                .retryWhen(errors -> errors
                        .zipWith(Observable.range(1, 3), (e, count) -> count)
                        .flatMap(retryCount -> Observable.timer((long) retryCount, TimeUnit.SECONDS))
                )
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SubscribedAck>() {

                    public void onNext(SubscribedAck response) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_success), name), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onSwipedRight", "subscribe", e);
                        MyUtils.onError(e, context);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        adapter.removeObject(channel);
        unsubscribe(channel.getDispersyCid(), channel.isSubscribed(), channel.getName());
    }

    void unsubscribe(final String dispersyCid, final boolean subscribed, final String name) {
        if (!subscribed) {
            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_already), name), Toast.LENGTH_SHORT).show();
            return;
        }

        rxSubs.add(service.unsubscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .doOnError(e -> {
                    if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_already), name), Toast.LENGTH_SHORT).show();
                    } else {
                        throw Exceptions.propagate(e);
                    }
                })
                .retryWhen(errors -> errors
                        .zipWith(Observable.range(1, 3), (e, count) -> count)
                        .flatMap(retryCount -> Observable.timer((long) retryCount, TimeUnit.SECONDS))
                )
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<UnsubscribedAck>() {

                    public void onNext(UnsubscribedAck response) {
                        Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_success), name), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onSwipedLeft", "unsubscribe", e);
                        MyUtils.onError(e, context);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerTorrent torrent) {
        switch (torrent.getCategory()) {
            case "Video":
                //TODO: watch later
                Toast.makeText(context, "watch now", Toast.LENGTH_SHORT).show();
                break;

            case "Audio":
                //TODO: listen later
                Toast.makeText(context, "listen now", Toast.LENGTH_SHORT).show();
                break;

            case "Document":
                //TODO: read later
                Toast.makeText(context, "read now", Toast.LENGTH_SHORT).show();
                break;

            case "Compressed":
            case "xxx":
            case "other":
                //TODO: download
                Toast.makeText(context, "download now", Toast.LENGTH_SHORT).show();
                break;
        }
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
                Toast.makeText(context, "read later", Toast.LENGTH_SHORT).show();
                break;

            case "Compressed":
            case "xxx":
            case "other":
                //TODO: download
                Toast.makeText(context, "queue download", Toast.LENGTH_SHORT).show();
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
