package org.tribler.android;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.widget.Toast;

import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
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
        Intent intent = MyUtils.viewChannelIntent(channel.getDispersyCid(), channel.getId(), channel.getName(), channel.isSubscribed());
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
        // Is already subscribed?
        if (channel.isSubscribed()) {
            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_already), channel.getName()), Toast.LENGTH_SHORT).show();
        } else {
            subscribe(channel.getDispersyCid(), channel.getName());
        }
    }

    Observable<SubscribedAck> subscribe(final String dispersyCid, final String name) {

        Observable<SubscribedAck> observable = service.subscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SubscribedAck>() {

                    public void onNext(SubscribedAck response) {
                        // Subscribed?
                        if (response.isSubscribed()) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Not subscribed to channel: %s \"%s\"", dispersyCid, name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                            // Already subscribed
                            Toast.makeText(context, String.format(context.getString(R.string.info_subscribe_already), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(DefaultInteractionListFragment.this, "subscribe", e);
                        }
                    }
                }));

        return observable;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        adapter.removeObject(channel);
        // Is already un-subscribed?
        if (!channel.isSubscribed()) {
            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_already), channel.getName()), Toast.LENGTH_SHORT).show();
        } else {
            unsubscribe(channel.getDispersyCid(), channel.getName());
        }
    }

    Observable<UnsubscribedAck> unsubscribe(final String dispersyCid, final String name) {

        Observable<UnsubscribedAck> observable = service.unsubscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .share();

        rxSubs.add(observable
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<UnsubscribedAck>() {

                    public void onNext(UnsubscribedAck response) {
                        // Un-subscribed?
                        if (response.isUnsubscribed()) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Not unsubscribed form channel: %s \"%s\"", dispersyCid, name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            // Already subscribed
                            Toast.makeText(context, String.format(context.getString(R.string.info_unsubscribe_already), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(DefaultInteractionListFragment.this, "unsubscribe", e);
                        }
                    }
                }));

        return observable;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerTorrent torrent) {
        String category = torrent.getCategory();
        if (category == null) {
            category = "";
        }
        switch (category) {
            case "Video":
                //TODO: watch now
                Toast.makeText(context, "watch now", Toast.LENGTH_SHORT).show();
                break;

            case "Audio":
                //TODO: listen now
                Toast.makeText(context, "listen now", Toast.LENGTH_SHORT).show();
                break;

            case "Document":
                //TODO: read now
                Toast.makeText(context, "read now", Toast.LENGTH_SHORT).show();
                break;

            case "Compressed":
            case "xxx":
            case "other":
                //TODO: download now
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

        // watch later?
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        adapter.removeObject(torrent);

        // not interested, never see again?
    }

}
