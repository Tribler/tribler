package org.tribler.android;

import android.net.Uri;
import android.support.design.widget.Snackbar;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Headers;
import okhttp3.Request;
import okhttp3.Response;

import static org.tribler.android.Triblerd.API;
import static org.tribler.android.Triblerd.BASE_URL;

public class SearchFragment extends TriblerViewFragment {
    public static final String TAG = SearchFragment.class.getSimpleName();

    private Call mSearchCall;

    private Callback mSearchCallback = new Callback() {

        /**
         * {@inheritDoc}
         */
        @Override
        public void onFailure(Call call, IOException e) {
            e.printStackTrace();
            Snackbar.make(getView(), e.getClass().getName(), Snackbar.LENGTH_LONG).show();
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
        if (mSearchCall != null) {
            mSearchCall.cancel();
            mAdapter.clear();
        }

        Request request = new Request.Builder()
                .url(BASE_URL + "/search?q=" + Uri.encode(query).toString())
                .build();

        mSearchCall = API.newCall(request);

        mSearchCall.enqueue(mSearchCallback);
    }

}
