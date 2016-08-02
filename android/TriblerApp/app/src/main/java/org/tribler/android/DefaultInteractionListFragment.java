package org.tribler.android;

import android.app.Activity;
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

    public static final int CHANNEL_ACTIVITY_REQUEST_CODE = 800;

    protected IRestApi service;
    private Context _context;

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
        _context = context;
        setInteractionListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        _context = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerChannel channel) {
        Intent intent = new Intent(_context, ChannelActivity.class);
        intent.setAction(Intent.ACTION_GET_CONTENT);
        intent.putExtra(Intent.EXTRA_TITLE, channel.getName());
        intent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, channel.getDispersyCid());
        intent.putExtra(ChannelActivity.EXTRA_SUBSCRIBED, channel.isSubscribed());
        startActivityForResult(intent, CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == CHANNEL_ACTIVITY_REQUEST_CODE) {
            if (resultCode == Activity.RESULT_FIRST_USER) {
                // Update the subscription status of the channel identified by dispersy_cid
                String dispersyCid = data.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
                boolean subscribed = data.getBooleanExtra(ChannelActivity.EXTRA_SUBSCRIBED, false);
                TriblerChannel channel = adapter.findByDispersyCid(dispersyCid);
                if (channel != null) {
                    channel.setSubscribed(subscribed);
                    // Update view
                    adapter.notifyObjectChanged(channel);
                }
            }
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

    protected void subscribe(final String dispersyCid, final boolean subscribed, final String name) {
        if (subscribed) {
            Toast.makeText(_context, name + ' ' + _context.getText(R.string.info_subscribe_already), Toast.LENGTH_SHORT).show();
            return;
        }

        rxSubs.add(service.subscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .retry(3)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SubscribedAck>() {

                    public void onNext(SubscribedAck response) {
                        Toast.makeText(_context, name + ' ' + _context.getText(R.string.info_subscribe_success), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                            Toast.makeText(_context, name + ' ' + _context.getText(R.string.info_subscribe_already), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("onSwipedRight", "subscribe", e);
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
        unsubscribe(channel.getDispersyCid(), channel.isSubscribed(), channel.getName());
    }

    protected void unsubscribe(final String dispersyCid, final boolean subscribed, final String name) {
        if (!subscribed) {
            Toast.makeText(_context, name + ' ' + _context.getText(R.string.info_unsubscribe_already), Toast.LENGTH_SHORT).show();
            return;
        }

        rxSubs.add(service.unsubscribe(dispersyCid)
                .subscribeOn(Schedulers.io())
                .retry(3)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<UnsubscribedAck>() {

                    public void onNext(UnsubscribedAck response) {
                        Toast.makeText(_context, name + ' ' + _context.getText(R.string.info_unsubscribe_success), Toast.LENGTH_SHORT).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            Toast.makeText(_context, name + ' ' + _context.getText(R.string.info_unsubscribe_already), Toast.LENGTH_SHORT).show();
                        } else {
                            Log.e("onSwipedLeft", "unsubscribe", e);
                        }
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
                Toast.makeText(_context, "watch now", Toast.LENGTH_SHORT).show();
                break;

            case "Audio":
                //TODO: listen later
                Toast.makeText(_context, "listen now", Toast.LENGTH_SHORT).show();
                break;

            case "Document":
                //TODO: read later
                Toast.makeText(_context, "read now", Toast.LENGTH_SHORT).show();
                break;

            case "Compressed":
            case "xxx":
            case "other":
                //TODO: download
                Toast.makeText(_context, "download now", Toast.LENGTH_SHORT).show();
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
                Toast.makeText(_context, "watch later", Toast.LENGTH_SHORT).show();
                break;

            case "Audio":
                //TODO: listen later
                Toast.makeText(_context, "listen later", Toast.LENGTH_SHORT).show();
                break;

            case "Document":
                //TODO: read later
                Toast.makeText(_context, "read later", Toast.LENGTH_SHORT).show();
                break;

            case "Compressed":
            case "xxx":
            case "other":
                //TODO: download
                Toast.makeText(_context, "queue download", Toast.LENGTH_SHORT).show();
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
