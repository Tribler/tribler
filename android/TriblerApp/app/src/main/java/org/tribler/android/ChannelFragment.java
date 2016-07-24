package org.tribler.android;

import android.net.Uri;
import android.util.Log;

import org.tribler.android.restapi.json.TriblerTorrent;

import java.util.List;

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
                .subscribe(new Observer<List<TriblerTorrent>>() {

                    public void onNext(List<TriblerTorrent> torrents) {
                        for (TriblerTorrent torrent : torrents) {
                            adapter.addObject(torrent);
                        }
                    }

                    public void onCompleted() {
                        Log.d(TAG, "Retrofit call 1 completed");
                    }

                    public void onError(Throwable e) {
                        Log.e(TAG, "Oops! We got an error while getting the list of contributors", e);
                    }
                }));
    }

}
