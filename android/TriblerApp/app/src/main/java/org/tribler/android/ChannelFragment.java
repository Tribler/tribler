package org.tribler.android;

import android.net.Uri;
import android.util.Log;

import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class ChannelFragment extends ListFragment {
    public static final String TAG = ChannelFragment.class.getSimpleName();

    public void getTorrents(String dispersyCid) {
        adapter.clear();

        subscriptions.add(service.getTorrents(Uri.encode(dispersyCid))
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
                        Log.e(TAG, "getTorrents", e);
                    }
                }));
    }
}
