package org.tribler.android;

import android.os.Bundle;
import android.util.Log;
import android.view.View;

import org.tribler.android.restapi.json.TriblerChannel;

import java.util.concurrent.TimeUnit;

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
        loadSubscribedChannels();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void reload() {
        super.reload();
        adapter.clear();
        loadSubscribedChannels();
    }

    private void loadSubscribedChannels() {
        loading = service.getSubscribedChannels()
                .subscribeOn(Schedulers.io())
                .retryWhen(errors -> errors
                        .zipWith(Observable.range(1, 3), (e, count) -> count)
                        .flatMap(retryCount -> Observable.timer((long) retryCount, TimeUnit.SECONDS))
                )
                .flatMap(response -> Observable.from(response.getSubscribed()))
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
                        Log.e("loadSubscribedChannels", "getSubscribed", e);
                        MyUtils.onError(e, context);
                    }
                });
        rxSubs.add(loading);
    }

}
