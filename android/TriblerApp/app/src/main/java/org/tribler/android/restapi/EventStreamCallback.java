package org.tribler.android.restapi;

import android.os.Handler;
import android.support.annotation.Nullable;
import android.text.TextUtils;
import android.util.Log;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonSyntaxException;

import org.tribler.android.restapi.json.ChannelDiscoveredEvent;
import org.tribler.android.restapi.json.EventContainer;
import org.tribler.android.restapi.json.EventsStartEvent;
import org.tribler.android.restapi.json.SearchResultChannelEvent;
import org.tribler.android.restapi.json.SearchResultTorrentEvent;
import org.tribler.android.restapi.json.TorrentDiscoveredEvent;
import org.tribler.android.restapi.json.TorrentRemovedFromChannelEvent;
import org.tribler.android.restapi.json.TriblerStartedEvent;
import org.tribler.android.restapi.json.UpgraderFinishedEvent;

import java.io.BufferedReader;
import java.io.IOException;
import java.net.ConnectException;
import java.util.ArrayList;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Headers;
import okhttp3.Response;

public class EventStreamCallback implements Callback {

    private boolean _ready = false;
    private final Gson _gson = new Gson();
    private final ArrayList<Handler> _eventHandlers = new ArrayList<>();

    public boolean isReady() {
        return _ready;
    }

    public boolean addEventHandler(Handler handler) {
        return _eventHandlers.add(handler);
    }

    public boolean removeEventHandler(Handler handler) {
        return _eventHandlers.remove(handler);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onFailure(Call call, IOException e) {
        _ready = false;
        if (e instanceof ConnectException) {
            Log.v("eventStream", e.getClass().getSimpleName() + ". " + e.getMessage());
        } else {
            Log.e("eventStream", e.getClass().getSimpleName() + ". " + e.getMessage(), e);
        }
        try {
            Thread.sleep(1000);
        } catch (InterruptedException ex) {
        }
        // Retry
        EventStream.openEventStream();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onResponse(Call call, Response response) throws IOException {
        if (!response.isSuccessful()) {
            _ready = false;
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
            _ready = true;

            // Blocking read
            while ((line = in.readLine()) != null) {
                line = line.trim();
                if (TextUtils.isEmpty(line)) {
                    continue;
                }
                Log.v("readLine", line);

                try {
                    //TODO: do not assume 1 event per 1 line and 1 line per 1 event
                    event = parseEvent(line);
                    if (event != null) {
                        Log.v("onEvent", event.getClass().getSimpleName() + "; handlers: " + _eventHandlers.size());

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
            _ready = false;
            Log.e("onResponse", "catch", ex);

            // Reconnect on timeout
            EventStream.openEventStream();
        }
    }

    @Nullable
    private Object parseEvent(String eventString) throws JsonSyntaxException {
        // Parse container to determine event type
        EventContainer container = _gson.fromJson(eventString, EventContainer.class);
        JsonElement event = container.getEvent();
        if (event == null) {
            Log.d("parseEvent", String.format("empty event body: %s", eventString));
            // Some event types have empty event body
            event = new JsonObject();
        }
        switch (container.getType()) {

            case EventsStartEvent.TYPE:
                return _gson.fromJson(event, EventsStartEvent.class);

            case UpgraderFinishedEvent.TYPE:
                return _gson.fromJson(event, UpgraderFinishedEvent.class);

            case TriblerStartedEvent.TYPE:
                return _gson.fromJson(event, TriblerStartedEvent.class);

            case SearchResultChannelEvent.TYPE:
                return _gson.fromJson(event, SearchResultChannelEvent.class);

            case SearchResultTorrentEvent.TYPE:
                return _gson.fromJson(event, SearchResultTorrentEvent.class);

            case ChannelDiscoveredEvent.TYPE:
                return _gson.fromJson(event, ChannelDiscoveredEvent.class);

            case TorrentDiscoveredEvent.TYPE:
                return _gson.fromJson(event, TorrentDiscoveredEvent.class);

            case TorrentRemovedFromChannelEvent.TYPE:
                return _gson.fromJson(event, TorrentRemovedFromChannelEvent.class);

            default:
                Log.e("parseEvent", String.format("Unknown event type: %s", container.getType()));
                return null;
        }
    }
}