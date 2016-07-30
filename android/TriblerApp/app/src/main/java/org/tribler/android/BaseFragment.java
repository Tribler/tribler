package org.tribler.android;

import android.os.Bundle;
import android.support.v4.app.Fragment;
import android.util.Log;

import rx.subscriptions.CompositeSubscription;

/**
 * Use RxJava CompositeSubscription to automatically un-subscribe onDestroy.
 */
public class BaseFragment extends Fragment {

    protected CompositeSubscription rxSubs;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.v(this.getClass().getSimpleName(), "onCreate");

        rxSubs = new CompositeSubscription();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.v(this.getClass().getSimpleName(), "onDestroy");

        // Memory leak detection
        MyUtils.getRefWatcher(getActivity()).watch(this);

        rxSubs.unsubscribe();
        rxSubs = null;
    }
}
