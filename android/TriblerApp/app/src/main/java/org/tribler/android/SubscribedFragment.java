package org.tribler.android;

import android.util.Log;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class SubscribedFragment extends ListFragment {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    public void getSubscriptions() {
        adapter.clear();

        subscriptions.add(service.getSubscribedChannels()
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .flatMap(response -> Observable.from(response.getSubscribed()))
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e(TAG, "getSubscribedChannels", e);
                    }
                }));
    }
}
