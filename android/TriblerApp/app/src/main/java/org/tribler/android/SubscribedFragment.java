package org.tribler.android;

import android.os.Bundle;
import android.util.Log;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class SubscribedFragment extends DefaultInteractionListFragment {

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadSubscriptions();
    }

    public void loadSubscriptions() {
        adapter.clear();

        rxSubs.add(service.getSubscribedChannels()
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getSubscribed()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("SubscribedFragment", "loadSubscriptions", e);
                    }
                }));
    }
}
