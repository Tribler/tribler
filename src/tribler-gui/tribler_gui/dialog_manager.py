from typing import List, Optional, Type


class DialogManager:
    """
    This class manages all dialogs that are created in the GUI.
    The only exception is the feedback dialog that is raised when an error occurs in the GUI.
    """
    dialogs: List["TriblerDialog"] = []  # noqa: F821

    @staticmethod
    def add_dialog(dialog: "TriblerDialog") -> None:  # noqa: F821
        DialogManager.dialogs.append(dialog)

    @staticmethod
    def remove_dialog(dialog: "TriblerDialog") -> None:  # noqa: F821
        if dialog in DialogManager.dialogs:
            DialogManager.dialogs.remove(dialog)

    @staticmethod
    def get_dialogs(diag_cls: Optional[Type]):
        """
        Return either all dialogs or dialogs with a specific type.
        """
        if not diag_cls:
            return DialogManager.dialogs
        return [dialog for dialog in DialogManager.dialogs if isinstance(dialog, diag_cls)]

    @staticmethod
    def close_all_dialogs(diag_cls: Optional[Type] = None) -> None:
        """
        Close all open dialogs or dialogs with a specific type.
        """
        to_close = DialogManager.get_dialogs(diag_cls) if diag_cls else DialogManager.dialogs
        for dialog in to_close:
            dialog.close_dialog()
