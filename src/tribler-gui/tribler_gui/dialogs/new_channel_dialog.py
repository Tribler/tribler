from tribler_gui.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog


class NewChannelDialog(ConfirmationDialog):
    def __init__(self, parent, create_channel_callback):
        super(NewChannelDialog, self).__init__(
            parent,
            "Create new channel",
            "Enter the name of the channel to create:",
            [('NEW', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            show_input=True,
        )

        # Submitting channel model is necessary because the model will trigger
        # some signals to update its on-screen data on adding a new subchannel
        # Also, the type of the created entity (channel vs collection) is decided
        # by the model. That is a rough hack, but works.
        self.create_channel_callback = create_channel_callback
        self.dialog_widget.dialog_input.setPlaceholderText('Channel name')
        self.dialog_widget.dialog_input.setFocus()
        self.button_clicked.connect(self.on_channel_name_dialog_done)
        self.show()

    def on_channel_name_dialog_done(self, action):
        if action == 0:
            text = self.dialog_widget.dialog_input.text()
            if text:
                self.create_channel_callback(channel_name=text)

        self.close_dialog()
