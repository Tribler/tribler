package org.tribler.android;

import android.os.Bundle;
import android.util.Log;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class DiscoveredFragment extends DefaultInteractionListFragment {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadDiscoveredChannels();
    }

    public void loadDiscoveredChannels() {
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
                        Log.e("DiscoveredFragment", "loadDiscoveredChannels", e);
                    }
                }));
    }
}
