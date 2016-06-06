package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import com.facebook.stetho.okhttp3.StethoInterceptor;

import org.kivy.android.PythonService;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;

public class Triblerd extends PythonService {

    public static final OkHttpClient API = new OkHttpClient.Builder()
            .addNetworkInterceptor(new StethoInterceptor()) // DEBUG
            .build();
    public static final int API_PORT = 8085;
    public static final String BASE_URL = "http://127.0.0.1:" + API_PORT;
    public static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, Triblerd.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("serviceEntrypoint", "Triblerd.py");
        intent.putExtra("pythonName", "Triblerd");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument", "-p " + API_PORT);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, Triblerd.class);
        ctx.stopService(intent);
    }

}
