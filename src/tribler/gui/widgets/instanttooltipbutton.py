from PyQt5.QtWidgets import QToolButton


class InstantTooltipButton(QToolButton):
    """
    This class represents a button that immediately shows a tooltip when being hovered over.
    Unfortunately, there are some issues in PyQt that makes it challenging to customize the background.
    For example, the background is not correctly clipped, also see https://stackoverflow.com/questions/39120586.
    Also, it seems that we are unable to modify the border-radius on tooltips without using a custom mask.
    """
