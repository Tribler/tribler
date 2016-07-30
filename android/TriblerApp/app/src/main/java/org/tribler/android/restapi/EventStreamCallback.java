package org.tribler.android.restapi;

import android.support.annotation.Nullable;
import android.util.Log;

import com.google.gson.Gson;

import org.tribler.android.restapi.json.ChannelDiscoveredEvent;
import org.tribler.android.restapi.json.EventContainer;
import org.tribler.android.restapi.json.EventsStartEvent;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;
import org.tribler.android.restapi.json.TorrentDiscoveredEvent;
import org.tribler.android.restapi.json.TriblerStartedEvent;
import org.tribler.android.restapi.json.UpgraderFinishedEvent;

import java.io.BufferedReader;
import java.io.IOException;
import java.util.ArrayList;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Headers;
import okhttp3.Response;

public class EventStreamCallback implements Callback {

    private static final Gson GSON = new Gson();

    private final ArrayList<IEventListener> _eventListeners = new ArrayList<>();

    public boolean addEventListener(IEventListener listener) {
        return _eventListeners.add(listener);
    }

    public boolean removeEventListener(IEventListener listener) {
        return _eventListeners.remove(listener);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onFailure(Call call, IOException ex) {
        Log.v("onFailure", "Service events stream not ready. Retrying in 1s...", ex);
        try {
            Thread.sleep(1000);
        } catch (InterruptedException e) {
        }
        // Retry until service comes up
        EventStream.openEventStream();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onResponse(Call call, Response response) throws IOException {
        if (!response.isSuccessful()) {
            throw new IOException(String.format("Response not successful: %s", response.toString()));
        }
        // Read headers
        Headers responseHeaders = response.headers();
        for (int i = 0, size = responseHeaders.size(); i < size; i++) {
            Log.v("responseHeaders", responseHeaders.name(i) + ": " + responseHeaders.value(i));
        }
        // Read body
        try {
            BufferedReader in = new BufferedReader(response.body().charStream());
            String line;
            // Blocking read
            while ((line = in.readLine()) != null) {
                Log.v("readLine", line);

                // Split events on the same line and restore delimiters
                String[] events = line.split("\\}\\{");
                for (int i = 1, j = events.length; i < j; i += 2) {
                    events[i - 1] += "}";
                    events[i] = "{" + events[i];
                }
                for (String eventString : events) {
                    Object event = parseEvent(eventString);
                    if (event != null) {
                        // Notify observers
                        for (IEventListener listener : _eventListeners) {
                            listener.onEvent(event);
                        }
                    }
                }
            }
            in.close();
        } catch (Exception ex) {
            Log.e("onResponse", "catch", ex);

            // Reconnect on timeout
            EventStream.openEventStream();
        }
    }

    @Nullable
    private static Object parseEvent(String eventString) {
        Log.v("parseEvent", eventString);

        EventContainer container = GSON.fromJson(eventString, EventContainer.class);
        Object event = container.getEvent();
        if (event == null) {
            eventString = "{}";
        } else {
            eventString = GSON.toJson(event);
        }
        switch (container.getType()) {

            case EventsStartEvent.TYPE:
                return GSON.fromJson(eventString, EventsStartEvent.class);

            case UpgraderFinishedEvent.TYPE:
                return GSON.fromJson(eventString, UpgraderFinishedEvent.class);

            case TriblerStartedEvent.TYPE:
                return GSON.fromJson(eventString, TriblerStartedEvent.class);

            case SearchResultChannelEvent.TYPE:
                return GSON.fromJson(eventString, SearchResultChannelEvent.class);

            case SearchResultTorrentEvent.TYPE:
                return GSON.fromJson(eventString, SearchResultTorrentEvent.class);

            case ChannelDiscoveredEvent.TYPE:
                return GSON.fromJson(eventString, ChannelDiscoveredEvent.class);

            case TorrentDiscoveredEvent.TYPE:
                return GSON.fromJson(eventString, TorrentDiscoveredEvent.class);

            default:
                Log.e("parseEvent", String.format("Unknown event type: %s", container.getType()));
                return null;
        }
    }
}