from PyQt5.QtWidgets import QTabWidget, QTreeWidgetItem
from TriblerGUI.defs import *
from TriblerGUI.utilities import format_size


class DownloadsDetailsTabWidget(QTabWidget):

    def update_with_download(self, download):
        self.window().download_detail_name_label.setText(download['name'])
        self.window().download_detail_status_label.setText(DLSTATUS_STRINGS[eval(download["status"])])
        self.window().download_detail_filesize_label.setText("%s in %d files" % (format_size(float(download["size"])), len(download["files"])))
        self.window().download_detail_health_label.setText("%d seeders, %d leechers" % (download["num_seeds"], download["num_peers"]))
        self.window().download_detail_infohash_label.setText(download['infohash'])

        # Populate the files list
        self.window().download_files_list.clear()
        for file in download["files"]:
            item = QTreeWidgetItem(self.window().download_files_list)
            item.setText(0, file["name"])
            item.setText(1, format_size(float(file["size"])))
            item.setText(2, '{percent:.1%}'.format(percent=file["progress"]))
            item.setText(3, "yes" if file["included"] else "no")
            self.window().download_files_list.addTopLevelItem(item)

        # Populate the trackers list
        self.window().download_trackers_list.clear()
        for tracker in download["trackers"]:
            item = QTreeWidgetItem(self.window().download_trackers_list)
            item.setText(0, tracker["url"])
            item.setText(1, tracker["status"])
            item.setText(2, str(tracker["peers"]))
