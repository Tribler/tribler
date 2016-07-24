package org.tribler.android;

import android.os.Bundle;
import android.util.Log;

import org.tribler.android.restapi.RestApiClient;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment implements RestApiClient.EventListener {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    public void startSearch(String query) {
        adapter.clear();

        subscriptions.add(service.startSearch(query)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e(TAG, "startSearch", e);
                    }
                }));
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        RestApiClient.setEventListener(this);
    }

    @Override
    public void onEventsStart() {

    }

    @Override
    public void onSearchResultChannel(String query, final TriblerChannel result) {
        getActivity().runOnUiThread(new Runnable() {
            @Override
            public void run() {
                adapter.addObject(result);
            }
        });
    }

    @Override
    public void onSearchResultTorrent(String query, final TriblerTorrent result) {
        getActivity().runOnUiThread(new Runnable() {
            @Override
            public void run() {
                adapter.addObject(result);
            }
        });
    }
}
