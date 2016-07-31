package org.tribler.android;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.util.Log;
import android.view.View;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;

import rx.Observer;
import rx.Subscription;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment implements Handler.Callback {

    private String _query;
    private Subscription _search;
    private Handler _eventHandler;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Start listening to events on the main thread so the gui can be updated
        _eventHandler = new Handler(Looper.getMainLooper(), this);
        EventStream.addHandler(_eventHandler);

        if (!EventStream.isReady()) {
            EventStream.openEventStream();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        EventStream.removeHandler(_eventHandler);
        super.onDestroy();
        _search = null;
        _eventHandler = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean handleMessage(Message message) {
        if (message.obj instanceof SearchResultChannelEvent) {
            SearchResultChannelEvent result = (SearchResultChannelEvent) message.obj;

            // Check if query is current
            if (_query.equalsIgnoreCase(result.getQuery())) {

                // Hide loading indicator
                progressBar.setVisibility(View.GONE);

                // Show search result
                adapter.addObject(result.getResult());
            } else {
                Log.w("ChannelSearchResult", _query + " != " + result.getQuery());
            }
        } else if (message.obj instanceof SearchResultTorrentEvent) {
            SearchResultTorrentEvent result = (SearchResultTorrentEvent) message.obj;

            // Check if query is current
            if (_query.equalsIgnoreCase(result.getQuery())) {

                // Hide loading indicator
                progressBar.setVisibility(View.GONE);

                // Show search result
                adapter.addObject(result.getResult());
            } else {
                Log.w("TorrentSearchResult", _query + " != " + result.getQuery());
            }
        }
        return true;
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

        // Show loading indicator
        progressBar.setVisibility(View.VISIBLE);

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
