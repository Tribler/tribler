package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.service.ExperimentService;

import java.util.HashMap;

public class ExperimentActivity extends MainActivity {

    private String experiment = null;

    protected void initService() {
        Intent intent = getIntent();
        if (intent != null) {
            Bundle extras = intent.getExtras();
            if (extras != null) {
                HashMap<String, Object> args = new HashMap<>(extras.size());
                for (String key : extras.keySet()) {
                    if ("experiment".equals(key)) {
                        experiment = extras.getString(key);
                    } else {
                        args.put(key, extras.get(key));
                    }
                }
                ExperimentService.start(this, experiment, args); // Run experiment
            }
        }
    }

    protected void killService() {
        ExperimentService.stop(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        EventStream.closeEventStream();
        statusBar.setText(String.format(getString(R.string.status_experiment), experiment));
        super.handleIntent(intent);
    }

}
