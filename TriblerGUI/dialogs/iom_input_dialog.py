from base64 import b64decode

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QImage
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QVBoxLayout

from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path


class IomInputDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, bank_name, required_input):
        DialogContainer.__init__(self, parent)

        self.required_input = required_input

        uic.loadUi(get_ui_file_path('iom_input_dialog.ui'), self.dialog_widget)

        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.confirm_button.clicked.connect(lambda: self.button_clicked.emit(1))

        if 'error_text' in required_input:
            self.dialog_widget.error_text_label.setText(required_input['error_text'])
        else:
            self.dialog_widget.error_text_label.hide()

        if 'image' in required_input['additional_data']:
            qimg = QImage()
            qimg.loadFromData(b64decode(required_input['additional_data']['image']))
            image = QPixmap.fromImage(qimg)
            scene = QGraphicsScene(self.dialog_widget.img_graphics_view)
            scene.addPixmap(image)
            self.dialog_widget.img_graphics_view.setScene(scene)
        else:
            self.dialog_widget.img_graphics_view.hide()

        self.dialog_widget.iom_input_title_label.setText(bank_name)

        vlayout = QVBoxLayout()
        self.dialog_widget.user_input_container.setLayout(vlayout)

        self.input_widgets = {}

        for specific_input in self.required_input['required_fields']:
            label_widget = QLabel(self.dialog_widget.user_input_container)
            label_widget.setText(specific_input['text'] + ":")
            label_widget.show()
            vlayout.addWidget(label_widget)

            input_widget = QLineEdit(self.dialog_widget.user_input_container)
            input_widget.setPlaceholderText(specific_input['placeholder'])
            if specific_input['type'] == 'password':
                input_widget.setEchoMode(QLineEdit.Password)

            input_widget.show()
            vlayout.addWidget(input_widget)
            self.input_widgets[specific_input['name']] = input_widget

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.dialog_widget.adjustSize()

        self.on_main_window_resize()
