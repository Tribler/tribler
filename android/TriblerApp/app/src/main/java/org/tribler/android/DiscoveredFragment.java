package org.tribler.android;

import android.util.Log;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class DiscoveredFragment extends ListFragment {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    public void getChannels() {
        adapter.clear();

        subscriptions.add(service.getDiscoveredChannels()
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .flatMap(response -> Observable.from(response.getChannels()))
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e(TAG, "getChannels", e);
                    }
                }));
    }
}
