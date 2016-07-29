package org.tribler.android;

import android.util.Log;

import org.tribler.android.restapi.json.QueriedAck;

import rx.Observer;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment {

    private String _query;

    public void startSearch(String query) {
        if (query == _query) {
            // Do not restart search
            return;
        }
        _query = query;

        adapter.clear();

        rxSubs.add(service.startSearch(query)
                .subscribeOn(Schedulers.io())
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("startSearch", "startSearch", e);
                    }
                }));

        //TODO: subscribe to event stream and listen for search results of this query
    }
}
