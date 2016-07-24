package org.tribler.android;

import android.net.Uri;
import android.os.Bundle;
import android.util.Log;

import org.tribler.android.restapi.RestApiClient;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Headers;
import okhttp3.Response;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class SearchFragment extends ListFragment implements RestApiClient.EventListener {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    public void startSearch(String query) {
        adapter.clear();

        subscriptions.add(service.startSearch(Uri.encode(query))
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e(TAG, "getSubscribedChannels", e);
                    }
                }));
    }

    private String _query;

    private Call _searchCall;

    private Callback _searchCallback = new Callback() {

        /**
         * {@inheritDoc}
         */
        @Override
        public void onFailure(Call call, IOException e) {
            e.printStackTrace();
        }

        /**
         * {@inheritDoc}
         */
        @Override
        public void onResponse(Call call, Response response) throws IOException {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected code " + response);
            }

            Headers responseHeaders = response.headers();
            for (int i = 0, size = responseHeaders.size(); i < size; i++) {
                System.out.println(responseHeaders.name(i) + ": " + responseHeaders.value(i));
            }

            System.out.println(response.body().string());
        }
    };

    /**
     * {@inheritDoc}
     */
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
        if (_query.equalsIgnoreCase(query)) {
            getActivity().runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    adapter.addObject(result);
                }
            });
        }
    }

    @Override
    public void onSearchResultTorrent(String query, final TriblerTorrent result) {
        if (_query.equalsIgnoreCase(query)) {
            getActivity().runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    adapter.addObject(result);
                }
            });
        }
    }
}
