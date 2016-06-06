package org.tribler.android;

import com.facebook.stetho.okhttp3.StethoInterceptor;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;

public class RestApiClient {

    public static final String BASE_URL = "http://127.0.0.1:" + Triblerd.REST_API_PORT;

    public static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    public static final OkHttpClient API = new OkHttpClient.Builder()
            .addNetworkInterceptor(new StethoInterceptor()) // DEBUG
            .build();

}
