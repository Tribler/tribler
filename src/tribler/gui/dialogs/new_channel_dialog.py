from tribler_gui.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.utilities import connect, tr


class NewChannelDialog(ConfirmationDialog):
    def __init__(self, parent, create_channel_callback):
        super().__init__(
            parent,
            tr("Create new channel"),
            tr("Enter the name of the channel/folder to create:"),
            [(tr("NEW"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
            show_input=True,
        )

        # Submitting channel model is necessary because the model will trigger
        # some signals to update its on-screen data on adding a new subchannel
        # Also, the type of the created entity (channel vs collection) is decided
        # by the model. That is a rough hack, but works.
        self.create_channel_callback = create_channel_callback
        self.dialog_widget.dialog_input.setPlaceholderText(tr("Channel name"))
        self.dialog_widget.dialog_input.setFocus()
        connect(self.button_clicked, self.on_channel_name_dialog_done)
        self.show()

    def on_channel_name_dialog_done(self, action):
        if action == 0:
            text = self.dialog_widget.dialog_input.text()
            if text:
                self.create_channel_callback(channel_name=text)

        self.close_dialog()
