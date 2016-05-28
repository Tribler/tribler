package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import org.kivy.android.PythonService;

public class ServiceTriblerd extends PythonService {

    public static int REST_API_PORT = 8085;

    @Override
    public boolean canDisplayNotification() {
        return false;
    }

    public static void start(Context ctx, String pythonServiceArgument) {
        Intent intent = new Intent(ctx, ServiceTriblerd.class);
        String argument = ctx.getFilesDir().getAbsolutePath();
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("serviceEntrypoint", "Triblerd.py");
        intent.putExtra("pythonName", "Triblerd");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument", pythonServiceArgument);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, ServiceTriblerd.class);
        ctx.stopService(intent);
    }

}