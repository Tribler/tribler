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

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String dispersyCid = getActivity().getIntent().getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
        loadTorrents(dispersyCid);
    }

    private void loadTorrents(final String dispersyCid) {
        adapter.clear();

        loading = service.getTorrents(dispersyCid)
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
                        loadTorrents(dispersyCid);
                    }
                });
        rxSubs.add(loading);
    }
}
