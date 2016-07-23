package org.tribler.android;

import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Request;
import okhttp3.Response;

import static org.tribler.android.RestApiClient.API;
import static org.tribler.android.RestApiClient.BASE_URL;

public class SubscribedFragment extends TriblerViewFragment {
    public static final String TAG = SubscribedFragment.class.getSimpleName();

    public void getSubscriptions() {
        Request request = new Request.Builder()
                .url(BASE_URL + "/channels/subscribed")
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
                if ("subscribed".equals(reader.nextName())) {
                    reader.beginArray();
                    while (reader.hasNext()) {
                        final TriblerChannel channel = gson.fromJson(reader, TriblerChannel.class);
                        getActivity().runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                mAdapter.addObject(channel);
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

