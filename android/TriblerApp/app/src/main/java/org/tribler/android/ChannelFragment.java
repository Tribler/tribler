package org.tribler.android;

import android.util.Log;

import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends DefaultInteractionListFragment {

    public void loadTorrents(String dispersyCid) {
        adapter.clear();

        subscriptions.add(service.getTorrents(dispersyCid)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .flatMap(response -> Observable.from(response.getTorrents()))
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("ChannelFragment", "loadTorrents", e);
                    }
                }));
    }
}
