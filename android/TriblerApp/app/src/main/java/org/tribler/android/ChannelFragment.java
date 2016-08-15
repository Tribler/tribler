package org.tribler.android;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.support.design.widget.Snackbar;
import android.support.v4.content.ContextCompat;
import android.util.Log;
import android.view.View;

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
    private Snackbar _snackbar;

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
    public void onDestroyView() {
        super.onDestroyView();
        _snackbar = null;
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
                View rootView = getView();
                if (rootView != null) {
                    // Notify user
                    String text = String.format(getString(R.string.info_content_discovered), torrent.getName());
                    if (_snackbar != null && _snackbar.isShownOrQueued()) {
                        _snackbar.setText(text);
                    } else {
                        _snackbar = Snackbar
                                .make(rootView, text, Snackbar.LENGTH_INDEFINITE)
                                .setAction(getText(R.string.action_REFRESH), view -> {
                                    // Update view
                                    reload();
                                });
                        _snackbar.setActionTextColor(ContextCompat.getColor(context, R.color.yellow));
                        _snackbar.show();
                    }
                }
            }
        }
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void reload() {
        super.reload();
        adapter.clear();
        loadTorrents();
    }

    private void loadTorrents() {
        loading = service.getTorrents(_dispersyCid)
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressView.setVisibility(View.GONE);
                        statusBar.setText("");
                    }

                    public void onError(Throwable e) {
                        Log.e("loadTorrents", "getTorrents", e);
                        MyUtils.onError(e, context);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException ex) {
                        }
                        // Retry
                        reload();
                    }
                });
        rxSubs.add(loading);
    }
}
