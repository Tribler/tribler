package org.tribler.android;

import android.util.Log;

import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends DefaultInteractionListFragment {

    private String _dispersyCid;

    public void loadTorrents(String dispersyCid) {
        if (dispersyCid == _dispersyCid) {
            // Do not reload
            return;
        }
        _dispersyCid = dispersyCid;

        adapter.clear();

        rxSubs.add(service.getTorrents(dispersyCid)
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        adapter.addObject(torrent);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("loadTorrents", "getTorrents", e);
                    }
                }));

        //TODO: subscribe to event stream and listen for newly torrents discovered in this channel
    }
}
