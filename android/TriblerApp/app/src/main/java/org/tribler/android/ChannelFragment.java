package org.tribler.android;

import android.util.Log;
import android.view.View;

import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends DefaultInteractionListFragment {

    private String _dispersyCid;

    public void loadTorrents(String dispersyCid) {
        if (dispersyCid.equals(_dispersyCid)) {
            // Do not reload
            return;
        }
        _dispersyCid = dispersyCid;

        adapter.clear();

        // Show loading indicator
        progressBar.setVisibility(View.VISIBLE);

        rxSubs.add(service.getTorrents(dispersyCid)
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressBar.setVisibility(View.GONE);
                    }

                    public void onError(Throwable e) {
                        Log.e("loadTorrents", "getTorrents", e);
                    }
                }));
    }
}
