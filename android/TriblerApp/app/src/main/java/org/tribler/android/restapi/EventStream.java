package org.tribler.android.restapi;

import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.ConnectionPool;
import okhttp3.OkHttpClient;
import okhttp3.Request;

public class EventStream {

    private static final OkHttpClient CLIENT = buildClient();

    private static final Request REQUEST = buildRequest("http://127.0.0.1:8088");

    private static final EventStreamCallback CALLBACK = new EventStreamCallback();

    private static Call CALL;

    /**
     * Static class
     */
    private EventStream() {
    }

    public static boolean addListener(IEventListener listener) {
        return CALLBACK.addEventListener(listener);
    }

    public static boolean removeListener(IEventListener listener) {
        return CALLBACK.removeEventListener(listener);
    }

    public static boolean openEventStream() {
        return openEventStream(false);
    }

    public static boolean openEventStream(boolean force) {
        return openEventStream(force, CLIENT, REQUEST, CALLBACK);
    }

    private static boolean openEventStream(boolean force, OkHttpClient client, Request request, Callback callback) {
        if (force || CALL == null) {
            if (CALL != null) {
                CALL.cancel();
            }
            CALL = client.newCall(request);
            CALL.enqueue(callback);
        }
        return CALLBACK.isReady();
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
