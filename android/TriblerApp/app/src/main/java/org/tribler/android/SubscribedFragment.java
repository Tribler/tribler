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
                .doOnError(e -> MyUtils.onError(e, this, null))
                .retryWhen(MyUtils::oneSecondDelay)
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
                        Log.e("getSubscribedChannels", e.getMessage(), e);
                        cancel();
                    }
                }));
    }

}
