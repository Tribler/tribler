package org.tribler.android;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.util.Log;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;

import rx.Observer;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment implements Handler.Callback {

    private String _query = "";
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
            SearchResultChannelEvent result = (SearchResultChannelEvent) message.obj;

            // Check if query is current
            if (_query.equalsIgnoreCase(result.getQuery())) {
                showLoading(false);

                // Show search result
                adapter.addObject(result.getResult());
            } else {
                Log.w("ChannelSearchResult", _query + " != " + result.getQuery());
            }
        } else if (message.obj instanceof SearchResultTorrentEvent) {
            SearchResultTorrentEvent result = (SearchResultTorrentEvent) message.obj;

            // Check if query is current
            if (_query.equalsIgnoreCase(result.getQuery())) {
                showLoading(false);

                // Show search result
                adapter.addObject(result.getResult());
            } else {
                Log.w("TorrentSearchResult", _query + " != " + result.getQuery());
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
        cancel();
        adapter.clear();

        showLoading(R.string.status_searching);

        // Start search
        rxSubs.add(loading = service.search(query)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::oneSecondDelay)
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
