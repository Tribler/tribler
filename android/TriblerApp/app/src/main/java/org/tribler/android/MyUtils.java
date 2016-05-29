package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Environment;
import android.os.Message;
import android.provider.MediaStore;
import android.util.Log;
import android.webkit.MimeTypeMap;

import com.google.gson.Gson;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import com.google.gson.stream.JsonWriter;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.math.BigDecimal;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

public class MyUtils {

    /**
     * Helper method to determine if the device has an extra-large screen. For
     * example, 10" tablets are extra-large.
     */
    public static boolean isXLargeTablet(Context context) {
        return (context.getResources().getConfiguration().screenLayout
                & Configuration.SCREENLAYOUT_SIZE_MASK) >= Configuration.SCREENLAYOUT_SIZE_XLARGE;
    }

    public static String getMimeType(Uri uri) {
        String type = null;
        String extension = MimeTypeMap.getFileExtensionFromUrl(uri.toString());
        if (extension != null) {
            type = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
        }
        return type;
    }

    public static Intent sendBeam(Uri uri, Context ctx) {
        Intent intent = new Intent(ctx, BeamActivity.class);
        intent.setAction(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(getMimeType(uri));
        return intent;
    }

    public static Intent sendChooser(Uri uri, CharSequence title) {
        Intent intent = new Intent();
        intent.setAction(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(getMimeType(uri));
        return Intent.createChooser(intent, title);
    }

    public static Intent captureVideo(Uri output) {
        Intent intent = new Intent(MediaStore.ACTION_VIDEO_CAPTURE);
        intent.putExtra(MediaStore.EXTRA_OUTPUT, output);
        intent.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, 1); // 0: low 1: high
        return intent;
    }

    /**
     * @return The file created for saving a video
     */
    public static File getOutputVideoFile(Context ctx) {
        File videoDir;
        if (Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState())) {
            videoDir = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_MOVIES).getAbsolutePath());
        } else {
            videoDir = new File(ctx.getFilesDir(), Environment.DIRECTORY_MOVIES);
        }
        // Create the storage directory if it does not exist
        if (!videoDir.exists() && !videoDir.mkdirs()) {
            Log.e(ctx.getClass().getName(), "Failed to create directory");
            return null;
        } else if (!videoDir.isDirectory()) {
            Log.e(ctx.getClass().getName(), "Not a directory");
            return null;
        }
        // Create a media file name
        String timeStamp = new SimpleDateFormat("yyyy-MM-dd_HH_mm_ss").format(new Date());
        return new File(videoDir, "VID_" + timeStamp + ".mp4");
    }

    public static Gson gson = new Gson();

    /**
     * This code reads a JSON document containing an array of messages.
     * It steps through array elements as a stream to avoid loading the complete document into memory.
     * It is concise because it uses Gson’s object-model to parse the individual messages:
     *
     * @param in
     * @return
     * @throws IOException
     */
    public static List<Message> readJsonStream(InputStream in) throws IOException {
        JsonReader reader = new JsonReader(new InputStreamReader(in, "UTF-8"));
        List<Message> messages = new ArrayList<Message>();
        reader.beginArray();
        while (reader.hasNext()) {
            Message message = gson.fromJson(reader, Message.class);
            messages.add(message);
        }
        reader.endArray();
        reader.close();
        return messages;
    }

    /**
     * This writes a JSON document containing an array of messages.
     * It benefits from the memory-efficiency of streaming and the conciseness of an object model:
     *
     * @param out
     * @param messages
     * @throws IOException
     */
    public static void writeJsonStream(OutputStream out, List<Message> messages) throws IOException {
        JsonWriter writer = new JsonWriter(new OutputStreamWriter(out, "UTF-8"));
        writer.setIndent("  ");
        writer.beginArray();
        for (Message message : messages) {
            gson.toJson(message, Message.class, writer);
        }
        writer.endArray();
        writer.close();
    }


    /**
     * This reads a stream of tokens from a JsonReader and writes them back to a JsonWriter.
     * It uses peek() to preview the next token, reads it, writes it, and loops until the token stream is exhausted.
     * Most applications will take more interesting actions based on the content of the tokens!
     *
     * @param reader
     * @param writer
     * @throws IOException
     */
    public static void prettyprint(JsonReader reader, JsonWriter writer) throws IOException {
        while (true) {
            JsonToken token = reader.peek();
            switch (token) {
                case BEGIN_ARRAY:
                    reader.beginArray();
                    writer.beginArray();
                    break;
                case END_ARRAY:
                    reader.endArray();
                    writer.endArray();
                    break;
                case BEGIN_OBJECT:
                    reader.beginObject();
                    writer.beginObject();
                    break;
                case END_OBJECT:
                    reader.endObject();
                    writer.endObject();
                    break;
                case NAME:
                    String name = reader.nextName();
                    writer.name(name);
                    break;
                case STRING:
                    String s = reader.nextString();
                    writer.value(s);
                    break;
                case NUMBER:
                    String n = reader.nextString();
                    writer.value(new BigDecimal(n));
                    break;
                case BOOLEAN:
                    boolean b = reader.nextBoolean();
                    writer.value(b);
                    break;
                case NULL:
                    reader.nextNull();
                    writer.nullValue();
                    break;
                case END_DOCUMENT:
                    return;
            }
        }
    }

}
