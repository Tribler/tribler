package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.View;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.IEventListener;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;

import rx.Observer;
import rx.Subscription;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment implements IEventListener {

    private String _query;
    private Subscription _search;

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
        _search = null;
        EventStream.removeListener(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityCreated(@Nullable Bundle savedInstanceState) {
        super.onActivityCreated(savedInstanceState);
        progressBar.setVisibility(View.GONE);
    }

    public void onEvent(Object event) {
        if (event instanceof SearchResultChannelEvent) {
            SearchResultChannelEvent result = (SearchResultChannelEvent) event;
            // Check query is current
            if (!_query.equalsIgnoreCase(result.getQuery())) {
                Log.w("ChannelSearchResult", _query + " != " + result.getQuery());
                return;
            }
            if (isDetached()) {
                adapter.addObject(result.getResult());
            } else {
                getActivity().runOnUiThread(() -> {
                    adapter.addObject(result.getResult());
                });
            }
        } else if (event instanceof SearchResultTorrentEvent) {
            SearchResultTorrentEvent result = (SearchResultTorrentEvent) event;
            // Check query is current
            if (!_query.equalsIgnoreCase(result.getQuery())) {
                Log.w("TorrentSearchResult", _query + " != " + result.getQuery());
                return;
            }
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

        // Cancel previous search
        if (_search != null && !_search.isUnsubscribed()) {
            _search.unsubscribe();
            rxSubs.remove(_search);
        }

        adapter.clear();

        // Start search
        _search = service.search(query)
                .subscribeOn(Schedulers.io())
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                        Log.v("startSearch", query);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("startSearch", "search", e);
                    }
                });
        rxSubs.add(_search);
    }
}
