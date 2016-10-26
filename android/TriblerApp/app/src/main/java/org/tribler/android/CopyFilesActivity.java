package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import org.tribler.android.restapi.EventStream;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

import rx.Observable;
import rx.Observer;
import rx.schedulers.Schedulers;

/**
 * TODO: SET exported="false" before public release!
 */
public class CopyFilesActivity extends MainActivity {

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        EventStream.closeEventStream();
        // Get parameters
        final Bundle extras = intent.getExtras();
        if (extras == null) {
            return;
        }
        rxSubs.add(Observable.from(extras.keySet())
                .observeOn(Schedulers.io())
                .subscribe(new Observer<String>() {

                    public void onNext(String key) {
                        Object value = extras.get(key);
                        if (value instanceof String) {
                            try {
                                copy(new File(key), new File((String) value));
                            } catch (IOException ex) {
                                onError(ex);
                            }
                        }
                    }

                    public void onCompleted() {
                        CopyFilesActivity.this.finish();
                    }

                    public void onError(Throwable e) {
                        Log.e("CopyFile", "onError", e);
                    }
                }));
    }

    private void copy(final File in, final File out) throws IOException {
        CopyFilesActivity.this.runOnUiThread(() -> showLoading("Copy file: " + in.getPath() + "\nTo: " + out.getPath()));

        InputStream input = new FileInputStream(in);
        OutputStream output = new FileOutputStream(out);

        Log.i("CopyFileStart", in.getPath());

        MyUtils.copy(input, output);

        Log.i("CopyFileDone", out.getPath());
    }

}
