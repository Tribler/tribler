package org.tribler.android;

import android.app.Fragment;

public class BaseFragment extends Fragment {

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        super.onDestroy();
        // Memory leak detection
        AppUtils.getRefWatcher(getActivity()).watch(this);
    }
}