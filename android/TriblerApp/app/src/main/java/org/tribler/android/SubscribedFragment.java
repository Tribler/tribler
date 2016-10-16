package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AppCompatActivity;

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
    public void onActivityCreated(@Nullable Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);

        // Set title
        if (context instanceof AppCompatActivity) {
            ActionBar actionBar = ((AppCompatActivity) context).getSupportActionBar();
            if (actionBar != null) {
                actionBar.setTitle(R.string.action_subscriptions);
            }
        }
    }

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
    protected void reload() {
        super.reload();
        loadSubscribedChannels();
    }

    private void loadSubscribedChannels() {
        rxSubs.add(loading = service.getSubscribedChannels()
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .flatMap(response -> Observable.from(response.getSubscribed()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerChannel>() {

                    public void onNext(TriblerChannel channel) {
                        adapter.addObject(channel);
                    }

                    public void onCompleted() {
                        showLoading(false);
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(SubscribedFragment.this, "getSubscribedChannels", e);
                    }
                }));
    }

}
