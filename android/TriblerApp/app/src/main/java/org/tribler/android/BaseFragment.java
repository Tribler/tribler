package org.tribler.android;

import android.content.Context;
import android.os.Bundle;
import android.support.v4.app.Fragment;
import android.util.Log;

import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;

import rx.subscriptions.CompositeSubscription;

/**
 * Use RxJava CompositeSubscription to automatically un-subscribe onDestroy and invalidateOptionsMenu.
 */
public class BaseFragment extends Fragment {

    protected Context context;
    protected CompositeSubscription rxSubs;
    protected CompositeSubscription rxMenuSubs;
    protected IRestApi service;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.v(this.getClass().getSimpleName(), "onCreate");

        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        service = TriblerService.createService(baseUrl, authToken);

        rxSubs = new CompositeSubscription();
        rxMenuSubs = new CompositeSubscription();
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

        rxMenuSubs.unsubscribe();
        rxMenuSubs = null;
        rxSubs.unsubscribe();
        rxSubs = null;

        service = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context ctx) {
        super.onAttach(ctx);
        Log.v(this.getClass().getSimpleName(), "onAttach");

        context = ctx;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDetach() {
        super.onDetach();
        Log.v(this.getClass().getSimpleName(), "onDetach");

        context = null;
    }

    public void invalidateOptionsMenu() {
        rxMenuSubs.unsubscribe();
        rxMenuSubs.clear();
        if (isAdded()) {
            getActivity().invalidateOptionsMenu();
        }
    }

}
