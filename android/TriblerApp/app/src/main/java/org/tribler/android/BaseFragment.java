package org.tribler.android;

import android.app.Fragment;

import com.squareup.leakcanary.RefWatcher;

public class BaseFragment extends Fragment {

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        RefWatcher refWatcher = TriblerApp.getInstance().getRefWatcher();
        refWatcher.watch(this);
    }
}