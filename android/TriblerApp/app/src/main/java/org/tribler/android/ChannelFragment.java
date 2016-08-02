package org.tribler.android;

import android.os.Bundle;
import android.util.Log;
import android.view.View;

import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends DefaultInteractionListFragment {

    private String _dispersyCid;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        _dispersyCid = getActivity().getIntent().getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
        loadTorrents();
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
                    }

                    public void onError(Throwable e) {
                        Log.e("loadTorrents", "getTorrents", e);
                        // Retry
                        reload();
                    }
                });
        rxSubs.add(loading);
    }
}
