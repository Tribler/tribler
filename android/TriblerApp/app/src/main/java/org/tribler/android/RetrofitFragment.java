package org.tribler.android;

import android.os.Bundle;

import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;

import rx.subscriptions.CompositeSubscription;

public class RetrofitFragment extends BaseFragment {

    protected CompositeSubscription subscriptions;
    protected IRestApi service;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        subscriptions = new CompositeSubscription();

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
        subscriptions.unsubscribe();
        subscriptions = null;
        service = null;
    }
}
