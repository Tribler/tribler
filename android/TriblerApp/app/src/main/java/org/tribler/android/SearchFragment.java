package org.tribler.android;

import android.net.Uri;
import android.os.Bundle;

import org.tribler.android.restapi.RestApiClient;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Headers;
import okhttp3.Request;
import okhttp3.Response;

import static org.tribler.android.restapi.RestApiClient.API;
import static org.tribler.android.restapi.RestApiClient.BASE_URL;

public class SearchFragment extends DefaultInteractionListFragment implements RestApiClient.EventListener {
    public static final String TAG = SearchFragment.class.getSimpleName();

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

    public void startSearch(String query) {
        if (_searchCall != null) {
            _searchCall.cancel();
            getActivity().runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    adapter.clear();
                }
            });
        }
        _query = query;

        Request request = new Request.Builder()
                .url(BASE_URL + "/search?q=" + Uri.encode(query))
                .build();

        _searchCall = API.newCall(request);

        _searchCall.enqueue(_searchCallback);
    }

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
