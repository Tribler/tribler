package org.tribler.android;

import android.os.Bundle;
import android.view.View;

import org.tribler.android.restapi.json.TriblerChannel;

import java.util.concurrent.TimeUnit;

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
        loadPopularChannels();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void reload() {
        super.reload();
        adapter.clear();
        loadPopularChannels();
    }

    private void loadPopularChannels() {
        loading = service.getPopularChannels(_limit)
                .subscribeOn(Schedulers.io())
                .doOnError(e -> MyUtils.onError("loadPopularChannels", context, e))
                .retryWhen(errors -> errors
                        .zipWith(Observable.range(1, 3), (e, count) -> count)
                        .flatMap(retryCount -> Observable.timer((long) retryCount, TimeUnit.SECONDS))
                )
                .flatMap(response -> Observable.from(response.getChannels()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressView.setVisibility(View.GONE);
                        statusBar.setText("");
                    }

                    public void onError(Throwable e) {
                        onCompleted();
                    }
                });
        rxSubs.add(loading);
    }
}
