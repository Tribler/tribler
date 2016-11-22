package org.tribler.android.videoserver;

import android.text.TextUtils;

import com.facebook.stetho.okhttp3.StethoInterceptor;

import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import retrofit2.Retrofit;
import retrofit2.adapter.rxjava.RxJavaCallAdapterFactory;
import retrofit2.converter.gson.GsonConverterFactory;

public class TriblerVideoService {

    /**
     * Static class
     */
    private TriblerVideoService() {
    }

    public static IVideoServerApi createService(final String baseUrl, final String authToken) {

        OkHttpClient.Builder okHttp = new OkHttpClient.Builder()
                .readTimeout(90, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .addNetworkInterceptor(new StethoInterceptor()) //DEBUG
                .retryOnConnectionFailure(true)
                .followSslRedirects(false)
                .followRedirects(false);

        return createService(baseUrl, authToken, okHttp);
    }

    public static IVideoServerApi createService(final String baseUrl, final String authToken, OkHttpClient.Builder okHttp) {

        Retrofit.Builder retrofit = new Retrofit.Builder()
                .addCallAdapterFactory(RxJavaCallAdapterFactory.create())
                .addConverterFactory(GsonConverterFactory.create())
                .baseUrl(baseUrl);

        if (!TextUtils.isEmpty(authToken)) {

            okHttp.addInterceptor(chain -> {
                Request request = chain.request();
                Request newReq = request.newBuilder()
                        .addHeader("Authorization", String.format("token %s", authToken))
                        .build();
                return chain.proceed(newReq);
            });
        }
        retrofit.client(okHttp.build());

        return retrofit.build().create(IVideoServerApi.class);
    }
}
