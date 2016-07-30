package org.tribler.android;

import android.os.Bundle;
import android.util.Log;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.IEventListener;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;

import rx.Observer;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment implements IEventListener {

    private String _query;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Start listening for search results on the event stream
        EventStream.addListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        EventStream.removeListener(this);
    }

    public void onEvent(Object event) {
        if (event instanceof SearchResultChannelEvent) {
            SearchResultChannelEvent result = (SearchResultChannelEvent) event;

            if (_query.equalsIgnoreCase(result.getQuery())) {
                if (isDetached()) {
                    adapter.addObject(result.getResult());
                } else {
                    getActivity().runOnUiThread(() -> {
                        adapter.addObject(result.getResult());
                    });
                }
            }
        } else if (event instanceof SearchResultTorrentEvent) {
            SearchResultTorrentEvent result = (SearchResultTorrentEvent) event;

            if (isDetached()) {
                adapter.addObject(result.getResult());
            } else {
                getActivity().runOnUiThread(() -> {
                    adapter.addObject(result.getResult());
                });
            }
        }
    }

    public void startSearch(String query) {
        if (query.equals(_query)) {
            // Do not restart search
            return;
        }
        _query = query;

        adapter.clear();

        // Start search
        rxSubs.add(service.search(query)
                .subscribeOn(Schedulers.io())
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                    }

                    public void onCompleted() {
                        Log.v("startSearch", query);
                    }

                    public void onError(Throwable e) {
                        Log.e("startSearch", "search", e);
                    }
                }));
    }
}
