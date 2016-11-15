package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.annotation.StringRes;
import android.support.design.widget.Snackbar;
import android.support.v4.content.ContextCompat;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.View;
import android.view.ViewGroup;

import butterknife.ButterKnife;
import butterknife.Unbinder;
import rx.subscriptions.CompositeSubscription;

/**
 * Use ButterKnife to automatically bind and unbind fields.
 * Use RxJava CompositeSubscription to automatically un-subscribe on invalidateOptionsMenu.
 */
public abstract class ViewFragment extends BaseFragment {

    private Unbinder _unbinder;
    private Snackbar _snackbar;

    @Nullable
    private CharSequence _statusMsg;

    protected CompositeSubscription rxViewSubs;
    protected CompositeSubscription rxMenuSubs;

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

        rxViewSubs = new CompositeSubscription();

        showLoading(_statusMsg);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyView() {
        super.onDestroyView();
        Log.v(getClass().getSimpleName(), "onDestroyView");

        dismissQuestion();

        rxViewSubs.unsubscribe();
        rxViewSubs = null;

        _unbinder.unbind();
        _unbinder = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        super.onCreateOptionsMenu(menu, inflater);
        Log.v(getClass().getSimpleName(), "onCreateOptionsMenu");

        rxMenuSubs = new CompositeSubscription();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroyOptionsMenu() {
        super.onDestroyOptionsMenu();
        Log.v(getClass().getSimpleName(), "onDestroyOptionsMenu");

        rxMenuSubs.unsubscribe();
        rxMenuSubs = null;
    }

    public void invalidateOptionsMenu() {
        Log.v(getClass().getSimpleName(), "invalidateOptionsMenu");

        rxMenuSubs.clear();
        if (isAdded()) {
            getActivity().invalidateOptionsMenu();
        }
    }

    protected void showLoading(@Nullable CharSequence text) {
        Log.v("showLoading", text == null ? "null" : text.toString());

        _statusMsg = text;
    }

    protected void showLoading(boolean show) {
        showLoading(show ? "" : null);
    }

    protected void showLoading(@StringRes int resId) {
        showLoading(getText(resId));
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
