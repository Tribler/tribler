package org.tribler.android.restapi;

import android.text.TextUtils;

import java.util.concurrent.TimeUnit;

import okhttp3.ConnectionPool;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import retrofit2.Retrofit;
import retrofit2.adapter.rxjava.RxJavaCallAdapterFactory;
import retrofit2.converter.gson.GsonConverterFactory;

public class TriblerService {

    /**
     * Static class
     */
    private TriblerService() {
    }

    public static IRestApi createService(final String baseUrl, final String authToken) {

        OkHttpClient client = new OkHttpClient.Builder()
                .connectionPool(new ConnectionPool(10, 10, TimeUnit.MINUTES))
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .followSslRedirects(false)
                .followRedirects(false)
                //.addNetworkInterceptor(new StethoInterceptor()) //DEBUG
                .build();

        Retrofit.Builder builder = new Retrofit.Builder()
                .addCallAdapterFactory(RxJavaCallAdapterFactory.create())
                .addConverterFactory(GsonConverterFactory.create())
                .baseUrl(baseUrl)
                .client(client);

        if (!TextUtils.isEmpty(authToken)) {

            client = new OkHttpClient.Builder()
                    .addInterceptor(chain -> {
                        Request request = chain.request();
                        Request newReq = request.newBuilder()
                                .addHeader("Authorization", String.format("token %s", authToken))
                                .build();
                        return chain.proceed(newReq);
                    })
                    //.addNetworkInterceptor(new StethoInterceptor()) //DEBUG
                    .build();

            builder.client(client);
        }

        return builder.build().create(IRestApi.class);
    }
}
