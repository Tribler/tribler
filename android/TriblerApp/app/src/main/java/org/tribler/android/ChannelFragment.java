package org.tribler.android;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.json.TorrentDiscoveredEvent;
import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends DefaultInteractionListFragment implements Handler.Callback {

    private String _dispersyCid;
    private Handler _eventHandler;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        _dispersyCid = getActivity().getIntent().getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
        loadTorrents();

        // Start listening to events on the main thread so the gui can be updated
        _eventHandler = new Handler(Looper.getMainLooper(), this);
        EventStream.addHandler(_eventHandler);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        EventStream.removeHandler(_eventHandler);
        super.onDestroy();
        _eventHandler = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean handleMessage(Message message) {
        if (message.obj instanceof TorrentDiscoveredEvent) {
            TorrentDiscoveredEvent torrent = (TorrentDiscoveredEvent) message.obj;

            // Check if torrent belongs to this channel
            if (_dispersyCid.equalsIgnoreCase(torrent.getDispersyCid())) {

                String question = String.format(getString(R.string.info_content_discovered), torrent.getName());
                askUser(question, R.string.action_REFRESH, view -> {
                    // Update view
                    reload();
                });
            }
        }
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void reload() {
        super.reload();
        loadTorrents();
    }

    private void loadTorrents() {
        rxSubs.add(loading = service.getTorrents(_dispersyCid)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                        showLoading(false);
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(ChannelFragment.this, "loadTorrents", e);
                    }
                }));
    }
}
