package org.tribler.android.restapi;

import android.util.Log;

import com.google.gson.Gson;

import org.tribler.android.SearchFragment;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;
import org.tribler.android.restapi.json.TriblerChannel;
import org.tribler.android.restapi.json.TriblerEvent;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.io.BufferedReader;
import java.io.IOException;
import java.lang.ref.WeakReference;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.ConnectionPool;
import okhttp3.Headers;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

@Deprecated
public class RestApiClient {
    public static final String TAG = SearchFragment.class.getSimpleName();

    private static final Gson GSON = new Gson();

    private static final OkHttpClient EVENTS = new OkHttpClient.Builder()
            .connectionPool(new ConnectionPool(1, 60, TimeUnit.MINUTES))
            .connectTimeout(1, TimeUnit.MINUTES)
            .readTimeout(60, TimeUnit.MINUTES)
            .writeTimeout(30, TimeUnit.SECONDS)
            //.addNetworkInterceptor(new StethoInterceptor()) //DEBUG
            .build();

    /**
     * Static class
     */
    private RestApiClient() {
    }

    private static WeakReference<EventListener> mEventListener;

    public static void setEventListener(EventListener listener) {
        mEventListener = new WeakReference<>(listener);
        // Start listening
        openEvents();
    }

    private static void openEvents() {
        Request request = new Request.Builder()
                .url("http://127.0.0.1:8088/events")
                .build();

        Log.d(TAG, "**************   (RE)CONNECT   ******************");
        EVENTS.newCall(request).enqueue(mEventCallback);
    }

    private static Callback mEventCallback = new Callback() {

        /**
         * {@inheritDoc}
         */
        @Override
        public void onFailure(Call call, IOException ex) {
            ex.printStackTrace();
            Log.v(TAG, "Service events stream not ready. Retrying in 1s...");
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
            }
            // Retry until service comes up
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
            // Read headers
            Headers responseHeaders = response.headers();
            for (int i = 0, size = responseHeaders.size(); i < size; i++) {
                Log.d(TAG, responseHeaders.name(i) + ": " + responseHeaders.value(i));
            }
            // Read body
            try {
                BufferedReader in = new BufferedReader(response.body().charStream());
                String line;
                // Blocking read
                while ((line = in.readLine()) != null) {
                    Log.v(TAG, line);
                    // Split events on the same line and restore delimiters
                    String[] events = line.split("\\}\\{");
                    for (int i = 1, j = events.length; i < j; i += 2) {
                        events[i - 1] += "}";
                        events[i] = "{" + events[i];
                    }
                    for (String eventString : events) {
                        Log.v(TAG, eventString);
                        parseEvent(eventString);
                    }
                }
                in.close();
            } catch (Exception e) {
                e.printStackTrace();
                // Reconnect on timeout
                openEvents();
            }
        }
    };

    private static void parseEvent(String eventString) throws IOException {
        EventListener listener = mEventListener.get();
        TriblerEvent event = GSON.fromJson(eventString, TriblerEvent.class);
        String eventJson = GSON.toJson(event.getEvent());
        switch (event.getType()) {
            case "events_start":
                Log.d(TAG, "------------- START EVENTS --------------");
                listener.onEventsStart();
                break;

            case "search_result_channel":
                SearchResultChannelEvent channelResult =
                        GSON.fromJson(eventJson, SearchResultChannelEvent.class);
                listener.onSearchResultChannel(channelResult.getQuery(), channelResult.getResult());
                break;

            case "search_result_torrent":
                SearchResultTorrentEvent torrentResult =
                        GSON.fromJson(eventJson, SearchResultTorrentEvent.class);
                listener.onSearchResultTorrent(torrentResult.getQuery(), torrentResult.getResult());
                break;

            default:
                Log.e(TAG, "------------- UNKNOWN EVENT --------------");
        }
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
}
