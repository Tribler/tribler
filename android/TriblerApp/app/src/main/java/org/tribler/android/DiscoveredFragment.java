package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class DiscoveredFragment extends DefaultInteractionListFragment {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    /**
     * {@inheritDoc}
     */
    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View view = super.onCreateView(inflater, container, savedInstanceState);

        loadDiscoveredChannels();

        return view;
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
                        Log.e(TAG, "loadDiscoveredChannels", e);
                    }
                }));
    }
}
