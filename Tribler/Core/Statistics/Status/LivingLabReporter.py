# Written by Njaal Borch
# see LICENSE.txt for license information

#
# Arno TODO: Merge with Core/Statistics/Status/*
#

import time
import sys

import httplib

import XmlPrinter
import xml.dom.minidom

import Status
from Tribler.Core.Utilities.timeouturlopen import find_proxy

STRESSTEST = False
DEBUG = False


class LivingLabPeriodicReporter(Status.PeriodicStatusReporter):
    """
    This reporter creates an XML report of the status elements
    that are registered and sends them using an HTTP Post at
    the given interval.  Made to work with the P2P-Next lab.
    """
    
    host = "p2pnext-statistics.comp.lancs.ac.uk"
    #path = "/testpost/"
    path = "/post/"
    
    def __init__(self, name, frequency, id, error_handler=None,
                 print_post=False):
        """
        Periodically report to the P2P-Next living lab status service

        name: The name of this reporter (ignored)
        frequency: How often (in seconds) to report
        id: The ID of this device (e.g. permid)
        error_handler: Optional error handler that will be called if the
        port fails
        print_post: Print post to stderr when posting to the lab (largely
        useful for debugging)
        
        """
        Status.PeriodicStatusReporter.__init__(self,
                                               name,
                                               frequency,
                                               error_handler)
        self.device_id = id
        self.print_post = print_post 
        self.num_reports = 0

    def new_element(self, doc, name, value):
        """
        Helper function to save some lines of code
        """

        element = doc.createElement(name)
        value = doc.createTextNode(str(value))
        element.appendChild(value)
        
        return element
        
    def report(self):
        """
        Create the report in XML and send it
        """

        # Create the report
        doc = xml.dom.minidom.Document()
        root = doc.createElement("nextsharedata")
        doc.appendChild(root)
        
        # Create the header
        header = doc.createElement("header")
        root.appendChild(header)
        header.appendChild(self.new_element(doc, "deviceid", self.device_id))
        header.appendChild(self.new_element(doc, "timestamp",
                                           long(round(time.time()))))
        
        version = "cs_v2a"
        header.appendChild(self.new_element(doc, "swversion", version))
        

        elements = self.get_elements()
        if len(elements) > 0:
        
            # Now add the status elements
            if len(elements) > 0:
                report = doc.createElement("event")
                root.appendChild(report)

                report.appendChild(self.new_element(doc, "attribute",
                                                   "statusreport"))
                report.appendChild(self.new_element(doc, "timestamp",
                                                   long(round(time.time()))))
                for element in elements:
                    print element.__class__
                    report.appendChild(self.new_element(doc,
                                                       element.get_name(),
                                                       element.get_value()))

        events = self.get_events()
        if len(events) > 0:
            for event in events:
                report = doc.createElement(event.get_type())
                root.appendChild(report)
                report.appendChild(self.new_element(doc, "attribute",
                                                   event.get_name()))
                if event.__class__ == Status.EventElement:
                    report.appendChild(self.new_element(doc, "timestamp",
                                                       event.get_time()))
                elif event.__class__ == Status.RangeElement:
                    report.appendChild(self.new_element(doc, "starttimestamp",
                                                       event.get_start_time()))
                    
                    report.appendChild(self.new_element(doc, "endtimestamp",
                                                       event.get_end_time()))
                for value in event.get_values():
                    report.appendChild(self.new_element(doc, "value", value))
                    
        if len(elements) == 0 and len(events) == 0:
            return # Was nothing here for us
        
        # all done
        xml_printer = XmlPrinter.XmlPrinter(root)
        if self.print_post:
            print >> sys.stderr, xml_printer.to_pretty_xml()
        xml_str = xml_printer.to_xml()

        # Now we send this to the service using a HTTP POST
        self.post(xml_str)

    def post(self, xml_str):
        """
        Post a status report to the living lab using multipart/form-data
        This is a bit on the messy side, but it does work
        """

        #print >>sys.stderr, xml_str
        
        self.num_reports += 1
        
        boundary = "------------------ThE_bOuNdArY_iS_hErE_$"
        headers = {"Host":self.host,
                   "User-Agent":"NextShare status reporter 2009.4",
                   "Content-Type":"multipart/form-data; boundary=" + boundary}

        base = ["--" + boundary]
        base.append('Content-Disposition: form-data; name="NextShareData"; filename="NextShareData"')
        base.append("Content-Type: text/xml")
        base.append("")
        base.append(xml_str)
        base.append("--" + boundary + "--")
        base.append("")
        base.append("")
        body = "\r\n".join(base)

        # Arno, 2010-03-09: Make proxy aware and use modern httplib classes
        wanturl = 'http://'+self.host+self.path
        proxyhost = find_proxy(wanturl)
        if proxyhost is None:
            desthost = self.host
            desturl = self.path
        else:
            desthost = proxyhost
            desturl = wanturl

        h = httplib.HTTPConnection(desthost)
        h.putrequest("POST", desturl)
        h.putheader("Host",self.host)
        h.putheader("User-Agent","NextShare status reporter 2010.3")
        h.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
        h.putheader("Content-Length",str(len(body)))
        h.endheaders()
        h.send(body)

        resp = h.getresponse()
        if DEBUG:
            # print >>sys.stderr, "LivingLabReporter:\n", xml_str
            print >>sys.stderr, "LivingLabReporter:", `resp.status`, `resp.reason`, "\n", resp.getheaders(), "\n", resp.read().replace("\\n", "\n")

        if resp.status != 200:
            if self.error_handler:
                try:
                    self.error_handler(resp.status, resp.read())
                except Exception, e:
                    pass
            else:
                print >> sys.stderr, "Error posting but no error handler:", \
                      errcode, h.file.read()
        

if __name__ == "__main__":
    """
    Small test routine to check an actual post (unittest checks locally)
    """

    status = Status.get_status_holder("UnitTest")
    def test_error_handler(code, message):
        """
        Test error-handler
        """
        print "Error:", code, message
        
    reporter = LivingLabPeriodicReporter("Living lab test reporter",
                                         1.0, test_error_handler)
    status.add_reporter(reporter)
    s = status.create_status_element("TestString", "A test string")
    s.set_value("Hi from Njaal")

    time.sleep(2)

    print "Stopping reporter"
    reporter.stop()

    print "Sent %d reports"% reporter.num_reports
