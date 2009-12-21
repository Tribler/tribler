# Written by Njaal Borch
# see LICENSE.txt for license information
#
# Arno TODO: move this to ../Tools/, wx not allowed in ../Core
#

import wx
import sys

import xmlrpclib
from base64 import decodestring
from Tribler.Core.ClosedSwarm import ClosedSwarm


class PaymentDialog(wx.Dialog):
    """
    The dialog to interact with the payment service
    TODO: Do some design here... :)
    """
    def __init__(self, swarm_title, payment_url, swarm_id, node_id):
        kwds = {"style":wx.DEFAULT_DIALOG_STYLE}
        wx.Dialog.__init__(self, None)

        self.payment_url = payment_url
        self.swarm_id = swarm_id
        self.node_id = node_id
        self.phone_number = None
        self.poa = None

        self.label_0 = wx.StaticText(self, -1, swarm_title)
        self.filler = wx.StaticText(self, -1, "")
        self.filler2 = wx.StaticText(self, -1, "")
        
        self.label_1 = wx.StaticText(self, -1, "Phone number")
        self.txt_phone_number = wx.TextCtrl(self, -1, "")
        self.btn_request_code = wx.Button(self, -1, "Request code")

        self.label_2 = wx.StaticText(self, -1, "Code")
        self.txt_code = wx.TextCtrl(self, -1, "")
        self.btn_send_code = wx.Button(self, -1, "Send code")
        

        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self._request_code, self.btn_request_code)
        self.Bind(wx.EVT_BUTTON, self._request_token, self.btn_send_code)


    def __set_properties(self):
        self.SetTitle("NextShare payment test")

        self.txt_code.Enable(False)
        self.btn_send_code.Enable(False)
        
    def __do_layout(self):
        # begin wxGlade: MyDialog.__do_layout
        grid_sizer_1 = wx.GridSizer(3, 3, 0, 0)

        # TODO: will be made properly when the dialog is implemented properly
        grid_sizer_1.Add(self.label_0, 0, 0, 0)
        grid_sizer_1.Add(self.filler, 0, 0, 0)
        grid_sizer_1.Add(self.filler2, 0, 0, 0)
        
        grid_sizer_1.Add(self.label_1, 0, 0, 0)
        grid_sizer_1.Add(self.txt_phone_number, 0, 0, 0)
        grid_sizer_1.Add(self.btn_request_code, 0, 0, 0)
        grid_sizer_1.Add(self.label_2, 0, 0, 0)
        grid_sizer_1.Add(self.txt_code, 0, 0, 0)
        grid_sizer_1.Add(self.btn_send_code, 0, 0, 0)
        self.SetSizer(grid_sizer_1)
        grid_sizer_1.Fit(self)
        self.Layout()
        # end wxGlade



    def _request_code(self, event):

        num = self.txt_phone_number.Value
        if not num:
            # TODO: Error handling
            return

        s = xmlrpclib.ServerProxy(self.payment_url)
        s.initialize_payment(num, self.swarm_id)

        # Enable code field and button
        self.phone_number = num
        self.txt_code.Enable(True)
        self.btn_send_code.Enable(True)
        
        
    def _request_token(self, event):

        code = self.txt_code.Value
        if not code:
            # TODO: Error handling
            return
        
        s = xmlrpclib.ServerProxy(self.payment_url)

        token = s.get_token(self.phone_number, code, self.swarm_id)

        # Got the token, now get the POA
        print "Got token, getting POA"
        
        poa = s.get_poa(token, self.swarm_id, self.node_id)
        
        self.poa = poa

        self.EndModal(0)

    def get_poa(self):
        return self.poa
        

def wx_get_poa(url, swarm_id, perm_id, root_window=None, swarm_title="Unknown content"):
    """
    Pop up a WX interface for the payment system
    """
    
    d = PaymentDialog(swarm_title,
                      url,
                      swarm_id,
                      perm_id)
    
    retval = d.ShowModal()
    poa_b64 = d.get_poa()
    poa_serialized = decodestring(poa_b64)
    poa = ClosedSwarm.POA.deserialize(poa_serialized)
    poa.verify()
    return poa
    
    

# Test
if __name__ == "__main__":

    app = wx.PySimpleApp()            
    import threading
    t = threading.Thread(target=app.MainLoop)
    t.start()

    

    d = PaymentDialog("Test file",
                      "http://localhost:9090",
                      "1234",
                      "myid")

    retval = d.ShowModal()
    print "Modal returned"
    poa_b64 = d.get_poa()
    if poa_b64:
        poa_serialized = decodestring(poa_b64)
        from Tribler.Core.ClosedSwarm import ClosedSwarm
        poa = ClosedSwarm.POA.deserialize(poa_serialized)
        poa.verify()
        print "Got valid poa"
        
    else:
        print "No POA for us..."
    
