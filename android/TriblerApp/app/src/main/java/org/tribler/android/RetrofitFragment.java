package org.tribler.android;

import android.os.Bundle;

import rx.subscriptions.CompositeSubscription;

public class RetrofitFragment extends BaseFragment {

    protected CompositeSubscription compositeSubscription;
    protected IRestApi service;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        compositeSubscription = new CompositeSubscription();

        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        service = TriblerService.createService(baseUrl, authToken);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        compositeSubscription.unsubscribe();
        compositeSubscription = null;
        service = null;
    }
}
