import wx
import string
import os

class BaseValidator(wx.PyValidator):

    def __init__(self):
        super(BaseValidator, self).__init__()

    def TransferToWindow(self):
        return True

    def TransferFromWindow(self):
        return True


class TextCtrlValidator(BaseValidator):

    CHECKTYPE_DIGIT = 1
    CHECKTYPE_ALPHA = 2

    def __init__(self, check_type=0):
        super(TextCtrlValidator, self).__init__()
        self._check_type = check_type

        self.Bind(wx.EVT_CHAR, self.OnChar)

    def Clone(self):
        return TextCtrlValidator(self._check_type)

    def Validate(self, win):
        edit_text = self.GetWindow()
        value = edit_text.GetValue()

        for ch in value:
            if self._check_type & self.CHECKTYPE_DIGIT:
                if ch not in string.digits:
                    return False
            if self._check_type & self.CHECKTYPE_ALPHA:
                if ch not in string.letters:
                    return False

        return True

    def OnChar(self, event):
        key = event.GetKeyCode()

        if key < wx.WXK_SPACE or key == wx.WXK_DELETE or key > 255:
            event.Skip()
            return

        if self._check_type & self.CHECKTYPE_DIGIT and chr(key) in string.digits:
            event.Skip()
            return

        if self._check_type & self.CHECKTYPE_ALPHA and chr(key) in string.letters:
            event.Skip()
            return

        if not wx.Validator_IsSilent():
            wx.Bell()

        return


class NumberValidator(BaseValidator):

    def __init__(self, min=None, max=None):
        super(NumberValidator, self).__init__()

        self._min = min
        self._max = max

        self.Bind(wx.EVT_CHAR, self.OnChar)

    def Clone(self):
        return NumberValidator(self._min, self._max)

    def Validate(self, win):
        edit_text = self.GetWindow()
        value = edit_text.GetValue()

        if not edit_text.IsEnabled():
            return True

        if not value:
            wx.MessageBox("Empty text", "Error",
                wx.OK | wx.ICON_ERROR, edit_text.GetParent())
            edit_text.SetValue(edit_text.original_text)
            return False
        for ch in value:
            if ch not in string.digits:
                return False

        new_value = int(value)
        if self._min is not None and new_value < self._min:
            wx.MessageBox("Number too small (%d < %d)" % (new_value, self._min), "Error",
                wx.OK | wx.ICON_ERROR, edit_text.GetParent())
            edit_text.SetValue(edit_text.original_text)
            return False

        if self._max is not None and new_value > self._max:
            wx.MessageBox("Number too big (%d > %d)" % (new_value, self._max), "Error",
                wx.OK | wx.ICON_ERROR, edit_text.GetParent())
            edit_text.SetValue(edit_text.original_text)
            return False

        return True

    def OnChar(self, event):
        key = event.GetKeyCode()
        value = event.GetEventObject().GetValue()

        if key < wx.WXK_SPACE or key == wx.WXK_DELETE or key > 255:
            event.Skip()
            return

        if chr(key) in string.digits:
            event.Skip()
            return

        if not wx.Validator_IsSilent():
            wx.Bell()

        return


class DirectoryValidator(BaseValidator):

    def __init__(self):
        super(DirectoryValidator, self).__init__()

    def Clone(self):
        return DirectoryValidator()

    def Validate(self, win):
        edit_text = self.GetWindow()
        value = edit_text.GetValue()

        is_valid = os.path.isdir(value)
        if not is_valid:
            wx.MessageBox("Invalid path [%s]" % value, "Error",
                wx.OK | wx.ICON_ERROR, edit_text.GetParent())
            edit_text.SetValue(edit_text.original_text)
        return is_valid


class NetworkSpeedValidator(BaseValidator):

    def __init__(self):
        super(NetworkSpeedValidator, self).__init__()

    def Clone(self):
        return NetworkSpeedValidator()

    def Validate(self, win):
        edit_text = self.GetWindow()
        value = edit_text.GetValue()

        if value == 'unlimited':
            return True
        if not value or any(ch not in string.digits for ch in value):
            wx.MessageBox("Empty network speed [%s]" % value, "Error",
                wx.OK | wx.ICON_ERROR, edit_text.GetParent())
            edit_text.SetValue(edit_text.original_text)
            return False
        return True
