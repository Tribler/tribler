package org.tribler.android.restapi.json;

public class MyChannelResponse {

    private OverviewPart overview;

    MyChannelResponse() {
    }

    public OverviewPart getOverview() {
        return overview;
    }

    class OverviewPart {

        private String name, description, identifier;

        OverviewPart() {
        }

        public String getName() {
            return name;
        }

        public String getDescription() {
            return description;
        }

        public String getIdentifier() {
            return identifier;
        }
    }

}