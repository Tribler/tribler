package org.tribler.android;

import android.app.Application;
import android.content.Context;

import com.squareup.leakcanary.LeakCanary;
import com.squareup.leakcanary.RefWatcher;

public class TriblerApp extends Application {

    public static RefWatcher getRefWatcher(Context context) {
        TriblerApp application = (TriblerApp) context.getApplicationContext();
        return application._refWatcher;
    }

    private RefWatcher _refWatcher;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate() {
        super.onCreate();
        _refWatcher = LeakCanary.install(this);
    }
}
