package org.tribler.android;

import android.text.TextUtils;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import retrofit2.Retrofit;
import retrofit2.adapter.rxjava.RxJavaCallAdapterFactory;
import retrofit2.converter.gson.GsonConverterFactory;

public class TriblerService {

    public static final String BASE_URL = "http://127.0.0.1:" + Triblerd.REST_API_PORT;

    /**
     * Static class
     */
    private TriblerService() {
    }

    public static IRestApi createService(final String authToken) {
        Retrofit.Builder builder = new Retrofit.Builder()
                .addCallAdapterFactory(RxJavaCallAdapterFactory.create())
                .addConverterFactory(GsonConverterFactory.create())
                .baseUrl(BASE_URL);

        if (!TextUtils.isEmpty(authToken)) {

            OkHttpClient client = new OkHttpClient.Builder()
                    .addInterceptor(chain -> {
                        Request request = chain.request();
                        Request newReq = request.newBuilder()
                                .addHeader("Authorization", String.format("token %s", authToken))
                                .build();
                        return chain.proceed(newReq);
                    }).build();

            builder.client(client);
        }

        return builder.build().create(IRestApi.class);
    }
}
