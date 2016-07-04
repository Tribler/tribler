package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import org.kivy.android.PythonService;

public class Triblerd extends PythonService {
    public static final int REST_API_PORT = 8085;

    /**
     * {@inheritDoc}
     */
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
        intent.putExtra("serviceTitle", "Tribler serivce");
        intent.putExtra("serviceDescription", "127.0.0.1:" + REST_API_PORT);
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
