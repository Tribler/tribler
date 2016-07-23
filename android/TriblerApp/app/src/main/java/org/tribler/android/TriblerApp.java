package org.tribler.android;


import android.app.Application;

import com.squareup.leakcanary.LeakCanary;
import com.squareup.leakcanary.RefWatcher;

public class TriblerApp extends Application {

    private static TriblerApp instance;
    private RefWatcher mRefWatcher;

    public static TriblerApp getInstance() {
        return instance;
    }

    public RefWatcher getRefWatcher() {
        return mRefWatcher;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        instance = (TriblerApp) getApplicationContext();
        mRefWatcher = LeakCanary.install(this);
    }
}
