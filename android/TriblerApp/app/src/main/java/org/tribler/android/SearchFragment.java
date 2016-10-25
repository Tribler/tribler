package org.tribler.android;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.support.annotation.Nullable;
import android.util.Log;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;

import rx.Observer;
import rx.Subscription;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment implements Handler.Callback {

    private String _query = "";
    private Handler _eventHandler;
    @Nullable
    private Subscription _search;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Start listening to events on the main thread so the gui can be updated
        _eventHandler = new Handler(Looper.getMainLooper(), this);
        EventStream.addHandler(_eventHandler);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        EventStream.removeHandler(_eventHandler);
        super.onDestroy();
        _eventHandler = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean handleMessage(Message message) {
        if (message.obj instanceof SearchResultChannelEvent) {
            SearchResultChannelEvent event = (SearchResultChannelEvent) message.obj;

            // Check if query is current
            if (_query.equalsIgnoreCase(event.getQuery())) {
                showLoading(false);

                // Show search result
                adapter.addObject(event.getResult());
            } else {
                Log.w("ChannelSearchResult", _query + " != " + event.getQuery());
            }
        } else if (message.obj instanceof SearchResultTorrentEvent) {
            SearchResultTorrentEvent event = (SearchResultTorrentEvent) message.obj;

            // Check if query is current
            if (_query.equalsIgnoreCase(event.getQuery())) {
                showLoading(false);

                // Show search result
                adapter.addObject(event.getResult());
            } else {
                Log.w("TorrentSearchResult", _query + " != " + event.getQuery());
            }
        }
        return true;
    }

    public void startSearch(final String query) {
        if (query.equals(_query)) {
            // Do not restart search
            return;
        }
        _query = query;

        // Cancel previous search
        if (_search != null) {
            _search.unsubscribe();
        }
        adapter.clear();

        showLoading(R.string.status_searching);

        // Start search
        rxSubs.add(_search = service.search(query)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                        Log.v("startSearch", query);
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(SearchFragment.this, "search", e);
                    }
                }));
    }
}
