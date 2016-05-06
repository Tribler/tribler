package org.kivy.android;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;

import org.renpy.android.AssetExtract;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.PackageManager.NameNotFoundException;
import android.os.Bundle;
import android.util.Log;

public class PythonActivity extends Activity {
	private static final String TAG = "PythonActivity";

	public static PythonActivity mActivity = null;

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		Log.v(TAG, "My oncreate running");

		Log.v(TAG, "Ready to unpack");
		unpackData("private", getFilesDir());

		Log.v(TAG, "About to do super onCreate");
		super.onCreate(savedInstanceState);
		Log.v(TAG, "Did super onCreate");

		mActivity = this;
	}

	public void loadLibraries() {
		PythonUtil.loadLibraries(getFilesDir());
	}

	public void recursiveDelete(File f) {
		if (f.isDirectory()) {
			for (File r : f.listFiles()) {
				recursiveDelete(r);
			}
		}
		f.delete();
	}

	public void unpackData(final String resource, File target) {

		Log.v(TAG, "UNPACKING!!! " + resource + " " + target.getName());

		// The version of data in memory and on disk.
		String data_version = null;
		String disk_version = null;

		try {
			PackageManager manager = this.getPackageManager();
			PackageInfo info = manager.getPackageInfo(this.getPackageName(), 0);
			data_version = info.versionName;

			Log.v(TAG, "Data version is " + data_version);
		} catch (NameNotFoundException e) {
			Log.w(TAG, "Data version not found of " + resource + " data.");
		}

		// If no version, no unpacking is necessary.
		if (data_version == null) {
			return;
		}

		// Check the current disk version, if any.
		String filesDir = target.getAbsolutePath();
		String disk_version_fn = filesDir + "/" + resource + ".version";

		try {
			byte buf[] = new byte[64];
			FileInputStream is = new FileInputStream(disk_version_fn);
			int len = is.read(buf);
			disk_version = new String(buf, 0, len);
			is.close();
		} catch (Exception e) {
			disk_version = "";
		}

		// If the disk data is out of date, extract it and write the version
		// file.
		if (!data_version.equals(disk_version)) {
			Log.v(TAG, "Extracting " + resource + " assets.");

			recursiveDelete(target);
			target.mkdirs();

			AssetExtract ae = new AssetExtract(this);
			if (!ae.extractTar(resource + ".mp3", target.getAbsolutePath())) {
				Log.e(TAG, "Could not extract " + resource + " data.");
			}

			try {
				// Write .nomedia.
				new File(target, ".nomedia").createNewFile();

				// Write version file.
				FileOutputStream os = new FileOutputStream(disk_version_fn);
				os.write(data_version.getBytes());
				os.close();
			} catch (Exception e) {
				Log.w("python", e);
			}
		}
	}

	public static void start_service(String serviceTitle,
			String serviceDescription, String pythonServiceArgument) {
		Intent serviceIntent = new Intent(PythonActivity.mActivity,
				PythonService.class);
		String argument = PythonActivity.mActivity.getFilesDir()
				.getAbsolutePath();
		String filesDirectory = argument;
		serviceIntent.putExtra("androidPrivate", argument);
		serviceIntent.putExtra("androidArgument", argument);
		serviceIntent.putExtra("serviceEntrypoint", "service/main.pyo");
		serviceIntent.putExtra("pythonHome", argument);
		serviceIntent.putExtra("pythonPath", argument + ":" + filesDirectory
				+ "/lib");
		serviceIntent.putExtra("serviceTitle", serviceTitle);
		serviceIntent.putExtra("serviceDescription", serviceDescription);
		serviceIntent.putExtra("pythonServiceArgument", pythonServiceArgument);
		PythonActivity.mActivity.startService(serviceIntent);
	}

	public static void stop_service() {
		Intent serviceIntent = new Intent(PythonActivity.mActivity,
				PythonService.class);
		PythonActivity.mActivity.stopService(serviceIntent);
	}

}
