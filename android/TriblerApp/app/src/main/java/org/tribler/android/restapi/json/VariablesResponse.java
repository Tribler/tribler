package org.tribler.android.restapi.json;

import java.util.Map;

public class VariablesResponse {

    private Map<String, Map<String, Object>> variables;

    VariablesResponse() {
    }

    public Map<String, Map<String, Object>> getVariables() {
        return variables;
    }

}
