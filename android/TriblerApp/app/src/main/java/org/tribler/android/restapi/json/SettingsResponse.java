package org.tribler.android.restapi.json;

import java.util.Map;

public class SettingsResponse {

    private Map<String, Map<String, Object>> settings;

    SettingsResponse() {
    }

    public Map<String, Map<String, Object>> getSettings() {
        return settings;
    }

}
