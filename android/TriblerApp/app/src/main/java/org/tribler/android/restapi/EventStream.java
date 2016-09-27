package org.tribler.android.restapi;

import android.os.Handler;

import com.facebook.stetho.okhttp3.StethoInterceptor;

import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.ConnectionPool;
import okhttp3.OkHttpClient;
import okhttp3.Request;

public class EventStream {

    private static final OkHttpClient CLIENT = buildClient();

    private static final Request REQUEST = buildRequest("http://127.0.0.1:8085");

    private static final EventStreamCallback CALLBACK = new EventStreamCallback();

    private static Call _call;

    /**
     * Static class
     */
    private EventStream() {
    }

    public static boolean addHandler(Handler handler) {
        return CALLBACK.addEventHandler(handler);
    }

    public static boolean removeHandler(Handler handler) {
        return CALLBACK.removeEventHandler(handler);
    }

    public static boolean isReady() {
        return CALLBACK.isReady();
    }

    public static void openEventStream() {
        newCall();
    }

    public static void closeEventStream() {
        close();
    }

    private static void newCall() {
        if (_call == null || !_call.isCanceled()) {
            _call = CLIENT.newCall(REQUEST);
            _call.enqueue(CALLBACK);
        }
    }

    private static void close() {
        if (_call != null) {
            _call.cancel();
        }
    }

    private static OkHttpClient buildClient() {
        return new OkHttpClient.Builder()
                .connectionPool(new ConnectionPool(1, 60, TimeUnit.MINUTES))
                .readTimeout(60, TimeUnit.MINUTES)
                .writeTimeout(30, TimeUnit.SECONDS)
                .addNetworkInterceptor(new StethoInterceptor()) //DEBUG
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
