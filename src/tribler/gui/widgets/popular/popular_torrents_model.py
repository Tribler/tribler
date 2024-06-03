from tribler.gui.widgets.tablecontentmodel import ChannelContentModel, Column


class PopularTorrentsModel(ChannelContentModel):
    columns_shown = (Column.CATEGORY, Column.NAME, Column.SIZE, Column.HEALTH, Column.CREATED)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, endpoint_url='metadata/torrents/popular', **kwargs)
