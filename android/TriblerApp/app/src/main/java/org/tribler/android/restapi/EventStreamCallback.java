package org.tribler.android.restapi;

import android.os.Handler;
import android.support.annotation.Nullable;
import android.text.TextUtils;
import android.util.Log;

import com.google.gson.Gson;
import com.google.gson.JsonSyntaxException;

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

    private static boolean ready = false;

    private static final Gson GSON = new Gson();

    private final ArrayList<Handler> _eventHandlers = new ArrayList<>();

    public boolean addEventHandler(Handler handler) {
        return _eventHandlers.add(handler);
    }

    public boolean removeEventHandler(Handler handler) {
        return _eventHandlers.remove(handler);
    }

    public boolean isReady() {
        return ready;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onFailure(Call call, IOException ex) {
        ready = false;
        Log.v("onFailure", "Service events stream not ready. Retrying in 1s...", ex);
        if (EventStream.isClosing()) {
            return;
        }
        try {
            Thread.sleep(1000);
        } catch (InterruptedException e) {
        }
        // Retry until service comes up
        EventStream.openEventStream(true);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onResponse(Call call, Response response) throws IOException {
        if (!response.isSuccessful()) {
            ready = false;
            throw new IOException(String.format("Response not successful: %s", response.toString()));
        }
        try {
            // Read headers
            Headers responseHeaders = response.headers();
            for (int i = 0, size = responseHeaders.size(); i < size; i++) {
                Log.v("responseHeaders", responseHeaders.name(i) + ": " + responseHeaders.value(i));
            }

            // Read body
            BufferedReader in = new BufferedReader(response.body().charStream());
            String line;
            Object event;
            ready = true;

            // Blocking read
            while ((line = in.readLine()) != null) {
                line = line.trim();
                if (TextUtils.isEmpty(line)) {
                    continue;
                }
                Log.v("readLine", line);

                try {
                    // TODO: do not assume 1 event per 1 line and 1 line per 1 event
                    event = parseEvent(line);
                    if (event != null) {
                        Log.v("onEvent", event.getClass().getSimpleName());

                        // Notify observers
                        for (int i = 0, j = _eventHandlers.size(); i < j; i++) {
                            _eventHandlers.get(i).obtainMessage(0, i, j, event).sendToTarget();
                        }
                    }
                } catch (JsonSyntaxException | NullPointerException e) {
                    Log.e("parseEvent", line, e);
                }
            }
            in.close();
        } catch (Exception ex) {
            ready = false;
            Log.e("onResponse", "catch", ex);

            // Reconnect on timeout
            EventStream.openEventStream(true);
        }
    }

    @Nullable
    private static Object parseEvent(String eventString) throws JsonSyntaxException {
        // Parse container to determine event type
        EventContainer container = GSON.fromJson(eventString, EventContainer.class);
        Object event = container.getEvent();
        if (event == null) {
            // Some event types have empty event body
            eventString = "{}";
        } else {
            // Turn body object back into json
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