package org.tribler.android.restapi;

import java.util.concurrent.TimeUnit;

import okhttp3.Callback;
import okhttp3.ConnectionPool;
import okhttp3.OkHttpClient;
import okhttp3.Request;

public class EventStream {

    private static final OkHttpClient CLIENT = buildClient();

    private static final Request REQUEST = buildRequest("http://127.0.0.1:8088");

    private static final EventStreamCallback CALLBACK = new EventStreamCallback();

    /**
     * Static class
     */
    private EventStream() {
    }

    public static void addListener(IEventListener listener) {
        CALLBACK.addEventListener(listener);
    }

    public static void removeListener(IEventListener listener) {
        CALLBACK.removeEventListener(listener);
    }

    public static void openEventStream() {
        openEventStream(CLIENT, REQUEST, CALLBACK);
    }

    private static void openEventStream(OkHttpClient client, Request request, Callback callback) {
        client.newCall(request).enqueue(callback);
    }

    private static OkHttpClient buildClient() {
        return new OkHttpClient.Builder()
                .connectionPool(new ConnectionPool(1, 60, TimeUnit.MINUTES))
                .readTimeout(60, TimeUnit.MINUTES)
                .writeTimeout(30, TimeUnit.SECONDS)
                //.addNetworkInterceptor(new StethoInterceptor()) //DEBUG
                .retryOnConnectionFailure(true)
                .followSslRedirects(false)
                .followRedirects(false)
                .build();
    }

    private static Request buildRequest(String baseUrl) {
        return new Request.Builder()
                .url(baseUrl + "/events")
                .build();
    }

}
