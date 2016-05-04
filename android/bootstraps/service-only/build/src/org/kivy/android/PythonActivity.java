package org.kivy.android;

import android.app.Activity;
import android.content.Intent;

public class PythonActivity extends Activity {

	public void start_service(String serviceTitle, String serviceDescription,
			String pythonServiceArgument) {
		Intent serviceIntent = new Intent(this, PythonService.class);
		String argument = this.getFilesDir().getAbsolutePath();
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
		this.startService(serviceIntent);
	}

	public void stop_service() {
		Intent serviceIntent = new Intent(this, PythonService.class);
		this.stopService(serviceIntent);
	}

}