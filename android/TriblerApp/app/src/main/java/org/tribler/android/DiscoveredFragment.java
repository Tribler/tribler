package org.tribler.android;

import android.support.design.widget.Snackbar;

import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Request;
import okhttp3.Response;

import static org.tribler.android.Triblerd.API;
import static org.tribler.android.Triblerd.BASE_URL;

public class DiscoveredFragment extends TriblerViewFragment {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    private Callback mCallback = new Callback() {

        /**
         * {@inheritDoc}
         */
        @Override
        public void onFailure(Call call, IOException e) {
            e.printStackTrace();
            Snackbar.make(getView(), e.getClass().getName(), Snackbar.LENGTH_LONG).show();
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
            if ("channels".equals(reader.nextName())) {
                reader.beginArray();
                while (reader.hasNext()) {
                    TriblerChannel channel = gson.fromJson(reader, TriblerChannel.class);
                    mAdapter.addItem(channel);
                }
                reader.endArray();
            } else {
                return;
            }
            reader.endObject();
        }

    };

    public void getDiscoveredChannels() {
        Request request = new Request.Builder()
                .url(BASE_URL + "/channels/discovered")
                .build();

        API.newCall(request).enqueue(mCallback);
    }

}
