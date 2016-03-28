from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QStackedWidget


class MyChannelPage(QWidget):

    def initialize_my_channel_page(self):
        self.my_channel_stacked_widget = self.findChild(QStackedWidget, "my_channel_stacked_widget")
        self.create_channel_form = self.findChild(QWidget, "create_channel_form")
        self.create_new_channel_intro_label = self.findChild(QLabel, "create_new_channel_intro_label")
        self.create_channel_intro_button = self.findChild(QPushButton, "create_channel_intro_button")
        self.create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.create_channel_intro_button_container = self.findChild(QWidget, "create_channel_intro_button_container")
        self.create_channel_form.hide()

        self.my_channel_stacked_widget.setCurrentIndex(1)

    def on_create_channel_intro_button_clicked(self):
        self.create_channel_form.show()
        self.create_channel_intro_button_container.hide()
        self.create_new_channel_intro_label.setText("Please enter your channel details below.")
