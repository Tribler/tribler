package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import com.loopj.android.http.AsyncHttpClient;

import org.kivy.android.PythonService;

public class Triblerd extends PythonService {

    public static final int REST_API_PORT = 8085;
    public static final String BASE_URL = "http://127.0.0.1/";
    public static final AsyncHttpClient restApi = new AsyncHttpClient(REST_API_PORT);

    @Override
    public boolean canDisplayNotification() {
        return false;
    }

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, Triblerd.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("serviceEntrypoint", "Triblerd.py");
        intent.putExtra("pythonName", "Triblerd");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument", "-p " + REST_API_PORT);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, Triblerd.class);
        ctx.stopService(intent);
    }

}