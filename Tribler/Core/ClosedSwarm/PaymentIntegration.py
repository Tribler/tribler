# Written by Njaal Borch
# see LICENSE.txt for license information
#
# Arno TODO: move this to ../Tools/, wx not allowed in ../Core
#

import wx
import sys
import urllib
import re

import xmlrpclib # Not needed for proper payment system integration
from base64 import encodestring,decodestring

from Tribler.Core.ClosedSwarm import ClosedSwarm


class PaymentSystem:

    def __init__(self, perm_id, swarm_id, mobile_number=None):
        self.mobile_number = mobile_number
        self.perm_id = perm_id
        self.swarm_id = swarm_id
        self.request_sent = None
        
    def set_phone_number(self, mobile_number):
        self.mobile_number = mobile_number


    def request_code(self):
        if self.request_sent == self.mobile_number:
            import sys
            print >> sys.stderr, "Refusing to send new request to same number"
            
        data = urllib.urlencode({"mobile": self.mobile_number, "request": "code", "swarm_id":self.swarm_id, "nosend": "off", "debug": "off"})
        
        f = urllib.urlopen("http://daccer.for-the.biz/smps.php", data)
        s = f.read()
        f.close()
        p = re.compile(r"error=(\S+)", re.MULTILINE)
        m = p.search(s)
        error = m.group(1)
        self.request_sent = self.mobile_number
        
        # TODO: Check for errors and throw exceptions
        return error

    def verify_code(self, code):
        import sys
        print >> sys.stderr, {"request": "validate", "code": code, "mobile": self.mobile_number, "perm_id": self.perm_id, "swarm_id": self.swarm_id}
        
        data = urllib.urlencode({"request": "validate", "code": code, "mobile": self.mobile_number, "perm_id": self.perm_id, "swarm_id": self.swarm_id})
        f = urllib.urlopen("http://daccer.for-the.biz/smps.php", data)
        s = f.read()
        f.close()
        p = re.compile(r"code=(\w+)", re.MULTILINE)
        m = p.search(s)
        if m != None:
            validation = m.group(1)
        else:
            validation = None
        p = re.compile(r"poa=(.*)..error=", re.DOTALL)
        m = p.search(s)
        if m != None:
            poa = m.group(1)
        else:
            poa = None
        p = re.compile(r"error=(\S+)", re.MULTILINE)
        m = p.search(s)
        if m != None:
            error = m.group(1)
        else:
            error = ",no_error_return"

        print >>sys.stderr,"Verify Code returned ",s,"with error:",error

        # TODO: Check for errors and throw exceptions
        return [validation, poa, error]

    


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

        self.label_0 = wx.StaticText(self, -1, "\nRegister your phone number (with country code) to get \nhigh speed access to the resource '" + swarm_title + "'\n")
        
        self.label_1 = wx.StaticText(self, -1, "Phone number")
        self.txt_phone_number = wx.TextCtrl(self, -1, "")
        self.btn_request_code = wx.Button(self, -1, "Request code")

        self.label_2 = wx.StaticText(self, -1, "Code")
        self.txt_code = wx.TextCtrl(self, -1, "")
        self.btn_send_code = wx.Button(self, -1, "Send code")
        
        self.status = wx.StatusBar(self, -1)
        
        self.__set_properties()
        self.__do_layout()

        self.Bind(wx.EVT_BUTTON, self._request_code, self.btn_request_code)
        self.Bind(wx.EVT_BUTTON, self._request_token, self.btn_send_code)

        self.status.SetStatusText("Please enter your phone number")

        self._payment_service = PaymentSystem(node_id, swarm_id)

    def __set_properties(self):
        self.SetTitle("NextShare payment test")

        self.txt_code.Enable(False)
        self.btn_send_code.Enable(False)
        
    def __do_layout(self):

        # begin wxGlade: MyDialog.__do_layout
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_1 = wx.GridSizer(2, 3, 0, 0)
        sizer_1.Add(self.label_0, 0, 0, 0)
        grid_sizer_1.Add(self.label_1, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.txt_phone_number, 0, wx.EXPAND, 0)
        grid_sizer_1.Add(self.btn_request_code, 0, wx.EXPAND, 0)
        grid_sizer_1.Add(self.label_2, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        grid_sizer_1.Add(self.txt_code, 0, wx.EXPAND, 0)
        grid_sizer_1.Add(self.btn_send_code, 0, wx.EXPAND, 0)
        sizer_1.Add(grid_sizer_1, 1, wx.EXPAND, 0)
        sizer_1.Add(self.status, 0, 0, 0)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)
        self.Layout()



    def _request_code(self, event):

        num = self.txt_phone_number.Value
        if not num:
            # TODO: Error handling
            return
        try:
            self._payment_service.set_phone_number(num.strip())
            self.status.SetStatusText("Requesting code...")
            error = self._payment_service.request_code()

            if error != "0":
                if error.count("mobile_number_wrong") > 0:
                    txt = "Bad mobile number"
                elif error.count("swarm_id_unavailable") > 0:
                    txt = "Unknown resource"
                else:
                    txt = "Unknown error: " + error
                    
                self.status.SetStatusText("Got errors:" + txt)
                return
            
        except Exception,e:
            print >>sys.stderr,"Error contacting payment system:",e
            # TODO: Handle errors properly
            return

        # TODO: Figure out why the payment system doesn't want the swarm ID
        # TODO: to figure out the price/availability etc.
        
        #s = xmlrpclib.ServerProxy(self.payment_url)
        #s.initialize_payment(num, self.swarm_id)

        # Enable code field and button
        self.phone_number = num
        self.txt_code.Enable(True)
        self.btn_send_code.Enable(True)
        
        self.status.SetStatusText("Please enter the code")
        
    def _request_token(self, event):

        code = self.txt_code.Value
        if not code:
            # TODO: Error handling
            return

        [validation, poa, error] = self._payment_service.verify_code(code)
        
        if error != "0":
            if error.count("no_such_code"):
                txt = "Bad code"
            elif error.count("code_to_old"):
                txt = "Code has expired"
            elif error.count("code_already_consumed"):
                txt = "This code has already been used"
            elif error.count("mobile_number_different"):
                txt = "INTERNAL: phone number has changed..."
            elif error.count("invalid_request"):
                txt = "The request vas invalid"
            else:
                txt = "Unknown error: " + error
            self.status.SetStatusText("Got error: " + txt)
            return
        
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
    try:
        poa_b64 = d.get_poa()
        poa_serialized = decodestring(poa_b64)
        poa = ClosedSwarm.POA.deserialize(poa_serialized)
        poa.verify()
        return poa
    except:
        return None

    

# Test
if __name__ == "__main__":

    app = wx.PySimpleApp()            
    import threading
    t = threading.Thread(target=app.MainLoop)
    t.start()

    

    d = PaymentDialog("Test file",
                      "http://127.0.0.1:9090",
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
    
