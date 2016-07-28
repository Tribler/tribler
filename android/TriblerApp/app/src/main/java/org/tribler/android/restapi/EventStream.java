package org.tribler.android.restapi;

import android.content.Context;

import org.tribler.android.R;
import org.tribler.android.restapi.json.TriblerEvent;

import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import rx.Observable;

public class EventStream {

    /**
     * Static class
     */
    private EventStream() {
    }

    private static Observable<TriblerEvent> _eventStream;

    public static Observable<TriblerEvent> getInstance(Context ctx) {
        if (_eventStream == null) {

            String baseUrl = ctx.getString(R.string.service_url) + ":" + ctx.getString(R.string.service_port_number);
            String authToken = ctx.getString(R.string.service_auth_token);

            OkHttpClient.Builder okHttp = new OkHttpClient.Builder()
                    .readTimeout(60, TimeUnit.MINUTES)
                    .writeTimeout(30, TimeUnit.SECONDS)
                    //.addNetworkInterceptor(new StethoInterceptor()) //DEBUG
                    .retryOnConnectionFailure(true)
                    .followSslRedirects(false)
                    .followRedirects(false);

            IRestApi api = TriblerService.createService(baseUrl, authToken, okHttp);

            _eventStream = api.getEventStream();
        }
        return _eventStream;
    }

}
