package org.tribler.android;

import android.os.Bundle;
import android.support.v4.app.Fragment;

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
        rxSubs = new CompositeSubscription();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        // Memory leak detection
        MyUtils.getRefWatcher(getActivity()).watch(this);

        rxSubs.unsubscribe();
        rxSubs = null;
    }
}
