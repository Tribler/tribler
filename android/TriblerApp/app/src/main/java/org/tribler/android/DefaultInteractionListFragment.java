package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;
import android.widget.Toast;

import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class DefaultInteractionListFragment extends ListFragment implements ListFragment.IListFragmentInteractionListener {
    public static final String TAG = DefaultInteractionListFragment.class.getSimpleName();

    private Context _context;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        _context = context;
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
        intent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, channel.getDispersyCid());
        intent.putExtra(Intent.EXTRA_TITLE, channel.getName());
        _context.startActivity(intent);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onClick(final TriblerTorrent torrent) {
        //TODO: play video
        Toast.makeText(_context, "play video", Toast.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerChannel channel) {
        if (channel.isSubscribed()) {
            Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_subscribe_already), Toast.LENGTH_LONG).show();
            return;
        }

        subscriptions.add(service.subscribe(Uri.encode(channel.getDispersyCid()))
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<SubscribedAck>() {

                    public void onNext(SubscribedAck response) {
                        Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_subscribe_success), Toast.LENGTH_LONG).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 409) {
                            Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_subscribe_already), Toast.LENGTH_LONG).show();
                        } else {
                            Log.e(TAG, "getSubscribedChannels", e);
                            Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_subscribe_failure), Toast.LENGTH_LONG).show();
                        }
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerChannel channel) {
        if (!channel.isSubscribed()) {
            Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_unsubscribe_already), Toast.LENGTH_LONG).show();
            return;
        }

        subscriptions.add(service.unsubscribe(Uri.encode(channel.getDispersyCid()))
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<UnsubscribedAck>() {

                    public void onNext(UnsubscribedAck response) {
                        Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_unsubscribe_success), Toast.LENGTH_LONG).show();
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_unsubscribe_already), Toast.LENGTH_LONG).show();
                        } else {
                            Log.e(TAG, "getSubscribedChannels", e);
                            Toast.makeText(_context, channel.getName() + ' ' + _context.getText(R.string.info_unsubscribe_failure), Toast.LENGTH_LONG).show();
                        }
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        //TODO: watch later
        Toast.makeText(_context, "watch later", Toast.LENGTH_LONG).show();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        //TODO: not interested
        //TODO: idea: never see torrent again?
        Toast.makeText(_context, "not interested", Toast.LENGTH_LONG).show();

    }

}
