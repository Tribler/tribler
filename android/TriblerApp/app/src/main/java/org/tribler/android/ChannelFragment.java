package org.tribler.android;

import android.net.Uri;

import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Request;
import okhttp3.Response;

import static org.tribler.android.RestApiClient.API;
import static org.tribler.android.RestApiClient.BASE_URL;

public class ChannelFragment extends DefaultInteractionListFragment {
    public static final String TAG = ChannelFragment.class.getSimpleName();

    public void getTorrents(String dispersyCid) {
        Request request = new Request.Builder()
                .url(BASE_URL + "/channels/discovered/" + Uri.encode(dispersyCid) + "/torrents")
                .build();

        Callback callback = new Callback() {

            /**
             * {@inheritDoc}
             */
            @Override
            public void onFailure(Call call, IOException e) {
                e.printStackTrace();
            }

            /**
             * {@inheritDoc}
             */
            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) {
                    throw new IOException("Unexpected code " + response);
                }

                Gson gson = new Gson();
                JsonReader reader = new JsonReader(response.body().charStream());

                reader.beginObject();
                if ("torrents".equals(reader.nextName())) {
                    reader.beginArray();
                    while (reader.hasNext()) {
                        final TriblerTorrent torrent = gson.fromJson(reader, TriblerTorrent.class);
                        getActivity().runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                adapter.addObject(torrent);
                            }
                        });
                    }
                    reader.endArray();
                } else {
                    throw new IOException("Invalid JSON");
                }
                reader.endObject();
            }

        };

        API.newCall(request).enqueue(callback);
    }

}
