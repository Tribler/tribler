package org.kivy.android;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.IBinder;
import android.os.Process;
import android.util.Log;

public class PythonService extends Service implements Runnable {

	// Thread for Python code
	private Thread pythonThread = null;

	// Python environment variables
	private String androidPrivate;
	private String androidArgument;
	private String pythonName;
	private String pythonHome;
	private String pythonPath;
	private String serviceEntrypoint;

	// Argument to pass to Python code,
	private String pythonServiceArgument;
	public static PythonService mService = null;
	private Intent startIntent = null;

	private boolean autoRestartService = false;

	public void setAutoRestartService(boolean restart) {
		autoRestartService = restart;
	}

	public boolean canDisplayNotification() {
		return true;
	}

	public int startType() {
		return START_NOT_STICKY;
	}

	@Override
	public IBinder onBind(Intent arg0) {
		return null;
	}

	@Override
	public void onCreate() {
		Log.v("PythonService", "Device: " + android.os.Build.DEVICE);
		Log.v("PythonService", "Model: " + android.os.Build.MODEL);
		super.onCreate();
	}

	@Override
	public int onStartCommand(Intent intent, int flags, int startId) {
		if (pythonThread != null) {
			Log.v("PythonService", "Service exists, do not start again");
			return START_NOT_STICKY;
		}

		startIntent = intent;
		Bundle extras = intent.getExtras();
		androidPrivate = extras.getString("androidPrivate");
		androidArgument = extras.getString("androidArgument");
		serviceEntrypoint = extras.getString("serviceEntrypoint");
		pythonName = extras.getString("pythonName");
		pythonHome = extras.getString("pythonHome");
		pythonPath = extras.getString("pythonPath");
		pythonServiceArgument = extras.getString("pythonServiceArgument");

		pythonThread = new Thread(this);
		pythonThread.start();

		if (canDisplayNotification()) {
			doStartForeground(extras);
		}

		return startType();
	}

	protected void doStartForeground(Bundle extras) {
		String serviceTitle = extras.getString("serviceTitle");
		String serviceDescription = extras.getString("serviceDescription");

		Context context = getApplicationContext();
		Notification notification = new Notification(
				context.getApplicationInfo().icon, serviceTitle,
				System.currentTimeMillis());
		Intent contextIntent = new Intent(context, PythonActivity.class);
		PendingIntent pIntent = PendingIntent.getActivity(context, 0,
				contextIntent, PendingIntent.FLAG_UPDATE_CURRENT);
		notification.setLatestEventInfo(context, serviceTitle,
				serviceDescription, pIntent);
		startForeground(1, notification);
	}

	@Override
	public void onDestroy() {
		super.onDestroy();
		pythonThread = null;
		if (autoRestartService && startIntent != null) {
			Log.v("PythonService", "Service restart requested");
			startService(startIntent);
		}
		Process.killProcess(Process.myPid());
	}

	@Override
	public void run() {
		PythonUtil.loadLibraries(getFilesDir());
		mService = this;
		nativeStart(androidPrivate, androidArgument, serviceEntrypoint,
				pythonName, pythonHome, pythonPath, pythonServiceArgument);
		stopSelf();
	}

	// Native part
	public static native void nativeStart(String androidPrivate,
			String androidArgument, String serviceEntrypoint,
			String pythonName, String pythonHome, String pythonPath,
			String pythonServiceArgument);
}
