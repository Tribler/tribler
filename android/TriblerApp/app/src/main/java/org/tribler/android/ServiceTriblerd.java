package org.tribler.android;

import android.content.Intent;
import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.util.Log;

import org.kivy.android.PythonService;
import org.kivy.android.PythonUtil;
import org.renpy.android.AssetExtract;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;

public class ServiceTriblerd extends PythonService {

    @Override
    public boolean canDisplayNotification() {
        return false;
    }

    static public void start(Context ctx, String pythonServiceArgument) {
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

    static public void stop(Context ctx) {
        Intent intent = new Intent(ctx, ServiceTriblerd.class);
        ctx.stopService(intent);
    }

}