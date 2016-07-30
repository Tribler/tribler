package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.View;

import butterknife.ButterKnife;
import butterknife.Unbinder;

/**
 * Use ButterKnife to automatically bind and unbind fields.
 */
public class ViewFragment extends BaseFragment {

    private Unbinder _unbinder;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onViewCreated(View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        Log.v(this.getClass().getSimpleName(), "onViewCreated");

        _unbinder = ButterKnife.bind(this, view);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        super.onDestroyView();
        Log.v(this.getClass().getSimpleName(), "onDestroyView");

        _unbinder.unbind();
        _unbinder = null;
    }
}
