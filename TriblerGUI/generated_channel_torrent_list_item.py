# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/martijndevos/Documents/tribler/TriblerGUI/qt_resources/channel_torrent_list_item.ui'
#
# Created by: PyQt5 UI code generator 5.6
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(585, 60)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form.sizePolicy().hasHeightForWidth())
        Form.setSizePolicy(sizePolicy)
        Form.setMinimumSize(QtCore.QSize(0, 60))
        Form.setMaximumSize(QtCore.QSize(16777215, 60))
        Form.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        Form.setStyleSheet("QWidget {\n"
"background-color: #666;\n"
"}")
        self.horizontalLayout = QtWidgets.QHBoxLayout(Form)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(10, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.thumbnail_widget = ThumbnailWidget(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.thumbnail_widget.sizePolicy().hasHeightForWidth())
        self.thumbnail_widget.setSizePolicy(sizePolicy)
        self.thumbnail_widget.setMinimumSize(QtCore.QSize(60, 42))
        self.thumbnail_widget.setMaximumSize(QtCore.QSize(60, 42))
        self.thumbnail_widget.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_widget.setObjectName("thumbnail_widget")
        self.horizontalLayout.addWidget(self.thumbnail_widget)
        spacerItem1 = QtWidgets.QSpacerItem(10, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        spacerItem2 = QtWidgets.QSpacerItem(20, 7, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalLayout.addItem(spacerItem2)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setSpacing(4)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.channel_torrent_category = QtWidgets.QLabel(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.channel_torrent_category.sizePolicy().hasHeightForWidth())
        self.channel_torrent_category.setSizePolicy(sizePolicy)
        self.channel_torrent_category.setMinimumSize(QtCore.QSize(0, 18))
        self.channel_torrent_category.setMaximumSize(QtCore.QSize(200, 18))
        self.channel_torrent_category.setStyleSheet("background-color: #bbb;\n"
"border-radius: 3px;\n"
"color: black;\n"
"font-size: 12px;\n"
"padding-left: 4px;\n"
"padding-right: 4px;")
        self.channel_torrent_category.setAlignment(QtCore.Qt.AlignCenter)
        self.channel_torrent_category.setObjectName("channel_torrent_category")
        self.horizontalLayout_3.addWidget(self.channel_torrent_category)
        self.channel_torrent_name = QtWidgets.QLabel(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.channel_torrent_name.sizePolicy().hasHeightForWidth())
        self.channel_torrent_name.setSizePolicy(sizePolicy)
        self.channel_torrent_name.setStyleSheet("color: #eee;\n"
"border: none;\n"
"background-color: transparent;\n"
"font-size: 15px;")
        self.channel_torrent_name.setObjectName("channel_torrent_name")
        self.horizontalLayout_3.addWidget(self.channel_torrent_name)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.channel_torrent_description = QtWidgets.QLabel(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.channel_torrent_description.sizePolicy().hasHeightForWidth())
        self.channel_torrent_description.setSizePolicy(sizePolicy)
        self.channel_torrent_description.setStyleSheet("color: #eee;\n"
"border: none;\n"
"background-color: transparent;\n"
"font-size: 15px;")
        self.channel_torrent_description.setObjectName("channel_torrent_description")
        self.horizontalLayout_2.addWidget(self.channel_torrent_description)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        spacerItem3 = QtWidgets.QSpacerItem(20, 7, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalLayout.addItem(spacerItem3)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.remove_control_button_container = QtWidgets.QWidget(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.remove_control_button_container.sizePolicy().hasHeightForWidth())
        self.remove_control_button_container.setSizePolicy(sizePolicy)
        self.remove_control_button_container.setMinimumSize(QtCore.QSize(0, 30))
        self.remove_control_button_container.setMaximumSize(QtCore.QSize(16777215, 30))
        self.remove_control_button_container.setStyleSheet("background-color: transparent;")
        self.remove_control_button_container.setObjectName("remove_control_button_container")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout(self.remove_control_button_container)
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.remove_torrent_button = QtWidgets.QToolButton(self.remove_control_button_container)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.remove_torrent_button.sizePolicy().hasHeightForWidth())
        self.remove_torrent_button.setSizePolicy(sizePolicy)
        self.remove_torrent_button.setMinimumSize(QtCore.QSize(24, 24))
        self.remove_torrent_button.setMaximumSize(QtCore.QSize(24, 24))
        self.remove_torrent_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.remove_torrent_button.setStyleSheet("background: none;\n"
"border: none;\n"
"background-color: #e67300;\n"
"border-radius: 2px;\n"
"color: white;\n"
"font-size: 12px;")
        self.remove_torrent_button.setText("")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("images/delete.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.remove_torrent_button.setIcon(icon)
        self.remove_torrent_button.setIconSize(QtCore.QSize(14, 14))
        self.remove_torrent_button.setObjectName("remove_torrent_button")
        self.horizontalLayout_4.addWidget(self.remove_torrent_button)
        self.horizontalLayout.addWidget(self.remove_control_button_container)
        self.control_buttons_container = QtWidgets.QWidget(Form)
        self.control_buttons_container.setStyleSheet("background-color: transparent;")
        self.control_buttons_container.setObjectName("control_buttons_container")
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout(self.control_buttons_container)
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_5.setSpacing(0)
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        spacerItem4 = QtWidgets.QSpacerItem(6, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem4)
        self.torrent_play_button = QtWidgets.QPushButton(self.control_buttons_container)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.torrent_play_button.sizePolicy().hasHeightForWidth())
        self.torrent_play_button.setSizePolicy(sizePolicy)
        self.torrent_play_button.setMinimumSize(QtCore.QSize(24, 24))
        self.torrent_play_button.setMaximumSize(QtCore.QSize(24, 24))
        self.torrent_play_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.torrent_play_button.setStyleSheet("border: none;\n"
"background-color: #e67300;\n"
"border-radius: 2px;")
        self.torrent_play_button.setText("")
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap("images/play.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.torrent_play_button.setIcon(icon1)
        self.torrent_play_button.setObjectName("torrent_play_button")
        self.horizontalLayout_5.addWidget(self.torrent_play_button)
        spacerItem5 = QtWidgets.QSpacerItem(6, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_5.addItem(spacerItem5)
        self.torrent_download_button = QtWidgets.QToolButton(self.control_buttons_container)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.torrent_download_button.sizePolicy().hasHeightForWidth())
        self.torrent_download_button.setSizePolicy(sizePolicy)
        self.torrent_download_button.setMinimumSize(QtCore.QSize(24, 24))
        self.torrent_download_button.setMaximumSize(QtCore.QSize(24, 24))
        self.torrent_download_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.torrent_download_button.setStyleSheet("background: none;\n"
"border: none;\n"
"background-color: #e67300;\n"
"border-radius: 2px;\n"
"color: white;\n"
"font-size: 12px;")
        self.torrent_download_button.setText("")
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap("images/downloads.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.torrent_download_button.setIcon(icon2)
        self.torrent_download_button.setObjectName("torrent_download_button")
        self.horizontalLayout_5.addWidget(self.torrent_download_button)
        self.horizontalLayout.addWidget(self.control_buttons_container)
        spacerItem6 = QtWidgets.QSpacerItem(14, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem6)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.thumbnail_widget.setText(_translate("Form", "PO"))
        self.channel_torrent_category.setText(_translate("Form", "video"))
        self.channel_torrent_name.setText(_translate("Form", "TextLabel"))
        self.channel_torrent_description.setText(_translate("Form", "384MB (3 files)"))

from thumbnailwidget import ThumbnailWidget
