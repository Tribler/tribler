package org.tribler.android;

import android.util.Log;

import com.facebook.stetho.okhttp3.StethoInterceptor;
import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.lang.ref.WeakReference;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.ConnectionPool;
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
            .connectionPool(new ConnectionPool(5, 5, TimeUnit.MINUTES))
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .addNetworkInterceptor(new StethoInterceptor()) // DEBUG
            .build();

    private static final OkHttpClient EVENTS = new OkHttpClient.Builder()
            .connectionPool(new ConnectionPool(1, 30, TimeUnit.MINUTES))
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.MINUTES)
            .writeTimeout(30, TimeUnit.SECONDS)
            .addNetworkInterceptor(new StethoInterceptor()) // DEBUG
            .build();

    private static final Gson GSON = new Gson();

    /**
     * Don't instantiate; all members and methods are static.
     */
    private RestApiClient() {
    }

    public interface EventListener {

        /**
         * An indication that the event socket is opened and that the server is ready to push events
         */
        void onEventsStart();

        /**
         * This event dictionary contains a search result with a channel that has been found
         */
        void onSearchResultChannel(String query, TriblerChannel result);

        /**
         * This event dictionary contains a search result with a torrent that has been found
         */
        void onSearchResultTorrent(String query, TriblerTorrent result);

    }

    private static WeakReference<EventListener> mEventListener;

    public static void setEventListener(EventListener listener) {
        mEventListener = new WeakReference<EventListener>(listener);

        // Start listening
        RestApiClient.openEvents();
    }

    private static Call mEventCall;

    private static Callback mEventCallback = new Callback() {

        /**
         * {@inheritDoc}
         */
        @Override
        public void onFailure(Call call, IOException ex) {
            ex.printStackTrace();
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
                BufferedReader in = new BufferedReader(response.body().charStream());
                String inputLine;
                while ((inputLine = in.readLine()) != null)
                    System.out.println(inputLine);
                in.close();
            } catch (Exception e) {
                e.printStackTrace();
                // Reconnect on timeout
                openEvents();
            }
        }
    };

    private static void openEvents() {
        Request request = new Request.Builder()
                .url(BASE_URL + "/events")
                .build();

        mEventCall = EVENTS.newCall(request);

        System.out.println("Open events stream");
        mEventCall.enqueue(mEventCallback);
    }

    private static void readEvents(JsonReader reader) throws IOException {
        String query;
        reader.beginObject();
        if ("type".equals(reader.nextName())) {

            switch (reader.nextString()) {
                case "events_start":
                    System.out.println("Events start");
                    mEventListener.get().onEventsStart();
                    break;

                case "search_result_channel":
                    if ("query".equals(reader.nextName())) {
                        query = reader.nextString();
                    } else {
                        throw new IOException("Invalid query");
                    }
                    TriblerChannel channel;
                    if ("result".equals(reader.nextName())) {
                        channel = GSON.fromJson(reader, TriblerChannel.class);
                    } else {
                        throw new IOException("Invalid result");
                    }
                    mEventListener.get().onSearchResultChannel(query, channel);
                    break;

                case "search_result_torrent":
                    if ("query".equals(reader.nextName())) {
                        query = reader.nextString();
                    } else {
                        throw new IOException("Invalid query");
                    }
                    TriblerTorrent torrent;
                    if ("result".equals(reader.nextName())) {
                        torrent = GSON.fromJson(reader, TriblerTorrent.class);
                    } else {
                        throw new IOException("Invalid result");
                    }
                    mEventListener.get().onSearchResultTorrent(query, torrent);
                    break;
            }
        } else {
            throw new IOException("Invalid type");
        }
        reader.endObject();
    }
}
