from PyQt5.QtWidgets import QProxyStyle, QStyle

from tribler_gui.widgets.instanttooltipbutton import InstantTooltipButton


class InstantTooltipStyle(QProxyStyle):
    """
    Proxy style to make sure that there is a zero tooltip delay for particular widgets.
    Specifically used to implement InstantTooltipButton.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if isinstance(widget, InstantTooltipButton) and hint == QStyle.SH_ToolTip_WakeUpDelay:
            return 0
        return QProxyStyle.styleHint(self, hint, option, widget, returnData)
