package org.tribler.android;

import android.os.Bundle;

import rx.subscriptions.CompositeSubscription;

public class RetrofitFragment extends BaseFragment {

    protected CompositeSubscription mCompositeSubscription;
    protected IRestApi mService;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        mCompositeSubscription = new CompositeSubscription();

        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        mService = TriblerService.createService(baseUrl, authToken);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        mCompositeSubscription.unsubscribe();
        mCompositeSubscription = null;
        mService = null;
    }
}
