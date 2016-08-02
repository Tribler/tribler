package org.tribler.android;

import android.os.Bundle;
import android.util.Log;
import android.view.View;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class PopularFragment extends DefaultInteractionListFragment {

    private int _limit = 50000;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadPopularChannels(_limit);
    }

    private void loadPopularChannels(final int limit) {
        adapter.clear();

        loading = service.getPopularChannels(limit)
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getChannels()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressView.setVisibility(View.GONE);
                    }

                    public void onError(Throwable e) {
                        Log.e("loadPopularChannels", "getChannels", e);
                        // Retry
                        loadPopularChannels(limit);
                    }
                });
        rxSubs.add(loading);
    }
}
