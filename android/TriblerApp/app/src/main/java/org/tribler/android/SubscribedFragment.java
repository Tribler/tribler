package org.tribler.android;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;

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

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == CHANNEL_ACTIVITY_REQUEST_CODE) {
            if (resultCode == Activity.RESULT_FIRST_USER) {

                // Show loading indicator
                progressView.setVisibility(View.VISIBLE);

                // Update view
                loadSubscriptions();
            }
        }
    }

    private void loadSubscriptions() {
        adapter.clear();

        loading = service.getSubscribedChannels()
                .subscribeOn(Schedulers.io())
                .retry(3)
                .flatMap(response -> Observable.from(response.getSubscribed()))
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
                        Log.e("loadSubscriptions", "getSubscribedChannels", e);
                    }
                });
        rxSubs.add(loading);
    }
}
