package org.tribler.android;

import android.util.Log;

import com.facebook.stetho.okhttp3.StethoInterceptor;

import java.io.IOException;
import java.net.SocketTimeoutException;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Headers;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class RestApiClient {
    public static final String TAG = SearchFragment.class.getSimpleName();

    public static final String BASE_URL = "http://127.0.0.1:" + Triblerd.REST_API_PORT;

    public static final MediaType TYPE_JSON = MediaType.parse("application/json; charset=utf-8");

    public static final OkHttpClient API = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .addNetworkInterceptor(new StethoInterceptor()) // DEBUG
            .build();

    private static final OkHttpClient EVENTS = new OkHttpClient.Builder()
            .readTimeout(60, TimeUnit.MINUTES)
            .addNetworkInterceptor(new StethoInterceptor()) // DEBUG
            .build();

    /**
     * Don't instantiate; all members and methods are static.
     */
    private RestApiClient() {
    }

    private static Call mEventCall;

    private static Callback mEventCallback = new Callback() {

        /**
         * {@inheritDoc}
         */
        @Override
        public void onFailure(Call call, IOException ex) {
            Log.v(TAG, "Service events stream not ready. Retrying in 1s...");
            // Retry until service comes up
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            openEvents();
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

            try {
                System.out.println(response.body().string());
            } catch (SocketTimeoutException e) {
                // Reconnect on timeout
                openEvents();
            }
        }
    };

    public static void openEvents() {
        Request request = new Request.Builder()
                .url(BASE_URL + "/events")
                .build();

        mEventCall = EVENTS.newCall(request);

        mEventCall.enqueue(mEventCallback);
    }
}
