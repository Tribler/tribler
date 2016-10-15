package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.annotation.StringRes;
import android.support.design.widget.Snackbar;
import android.support.v4.content.ContextCompat;
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
    private Snackbar _snackbar;

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

        dismissQuestion();

        _unbinder.unbind();
        _unbinder = null;
    }

    protected boolean askUser(CharSequence question, @StringRes int resId, final View.OnClickListener listener) {
        View rootView = getView();
        if (rootView != null && rootView.isShown()) {

            if (_snackbar != null && _snackbar.isShownOrQueued()) {
                _snackbar.setText(question);
            } else {
                _snackbar = Snackbar
                        .make(rootView, question, Snackbar.LENGTH_INDEFINITE)
                        .setAction(resId, listener)
                        .setActionTextColor(ContextCompat.getColor(context, R.color.yellow));
                _snackbar.show();
            }
            return true;
        }
        return false;
    }

    protected void dismissQuestion() {
        if (_snackbar != null) {
            _snackbar.setAction("", null);
            _snackbar.dismiss();
        }
        _snackbar = null;
    }

}
