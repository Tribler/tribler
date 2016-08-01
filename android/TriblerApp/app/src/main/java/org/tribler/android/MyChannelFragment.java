package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.View;

import org.tribler.android.restapi.json.TriblerChannel;

import rx.Observable;
import rx.Observer;
import rx.Subscription;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MyChannelFragment extends DefaultInteractionListFragment {

    private Subscription _loading;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadMyChannel();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        _loading = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        super.onCreateOptionsMenu(menu, inflater);
        inflater.inflate(R.menu.menu_my_channel, menu);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onViewCreated(View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        if (!_loading.isUnsubscribed()) {
            // Show loading indicator
            progressBar.setVisibility(View.VISIBLE);
        }
    }

    private void loadMyChannel() {
        adapter.clear();

        _loading = service.getPopularChannels(5)
                .subscribeOn(Schedulers.io())
                .flatMap(response -> Observable.from(response.getChannels()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                        // Hide loading indicator
                        progressBar.setVisibility(View.GONE);
                    }

                    public void onError(Throwable e) {
                        Log.e("loadMyChannel", "getChannels", e);
                    }
                });
        rxSubs.add(_loading);
    }
}
