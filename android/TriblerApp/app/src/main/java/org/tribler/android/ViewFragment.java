package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import butterknife.ButterKnife;
import butterknife.Unbinder;

/**
 * Use ButterKnife to automatically bind and unbind fields.
 */
public abstract class ViewFragment extends BaseFragment {

    private Unbinder _unbinder;

    /**
     * {@inheritDoc}
     */
    @Override
    public abstract View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState);

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
