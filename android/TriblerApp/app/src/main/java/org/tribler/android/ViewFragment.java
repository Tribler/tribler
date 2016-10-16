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
        Log.v(getClass().getSimpleName(), "onViewCreated");

        _unbinder = ButterKnife.bind(this, view);

        if (loading != null && !loading.isUnsubscribed()) {
            showLoading(true);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        super.onDestroyView();
        Log.v(getClass().getSimpleName(), "onDestroyView");

        dismissQuestion();

        _unbinder.unbind();
        _unbinder = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void cancel() {
        super.cancel();

        if (_unbinder != null) {
            showLoading(false);
        }
    }

    protected void reload() {
        cancel();
        showLoading(true);
    }

    protected abstract void showLoading(boolean show, @Nullable CharSequence text);

    protected void showLoading(boolean show) {
        showLoading(show, null);
    }

    protected void showLoading(@StringRes int resId) {
        showLoading(true, getText(resId));
    }

    /**
     * @param question The question to ask the user
     * @param resId    Action button text
     * @param listener Action listener
     * @return True if question is asked, false otherwise
     */
    protected boolean askUser(CharSequence question, @StringRes int resId, final View.OnClickListener listener) {
        View rootView = getView();
        if (rootView == null) {
            Log.w("askUser", "rootView == null", new NullPointerException());
            return false;
        }
        if (_snackbar != null) {
            _snackbar.setText(question);
        } else {
            _snackbar = Snackbar
                    .make(rootView, question, Snackbar.LENGTH_INDEFINITE)
                    .setAction(resId, listener)
                    .setActionTextColor(ContextCompat.getColor(context, R.color.yellow));
        }
        _snackbar.show();
        return true;
    }

    protected void dismissQuestion() {
        if (_snackbar != null) {
            _snackbar.setAction("", null);
            _snackbar.dismiss();
        }
        _snackbar = null;
    }

}
