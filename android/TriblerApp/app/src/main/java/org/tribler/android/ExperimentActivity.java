package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.Toast;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.service.ExperimentService;

import java.util.HashMap;

public class ExperimentActivity extends MainActivity {

    protected void startService() {
        /** @see handleIntent
         */
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
        // Get parameters
        Bundle extras = intent.getExtras();
        if (extras != null) {
            HashMap<String, Object> args = new HashMap<>(extras.size());
            String experiment = null;
            for (String key : extras.keySet()) {
                if ("experiment".equals(key)) {
                    experiment = extras.getString(key);
                } else {
                    args.put(key, extras.get(key));
                }
            }
            if (experiment != null) {
                ExperimentService.start(ExperimentActivity.this, experiment, args); // Run experiment
                Toast.makeText(ExperimentActivity.this, String.format(getString(R.string.status_experiment), experiment), Toast.LENGTH_LONG).show();
                finish();
            } else {
                Log.e("Experiment", "null");
            }
        }
    }

}
