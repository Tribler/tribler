import time

import urllib
import httplib

import XmlPrinter
import xml.dom.minidom

import Status

class LivingLabPeriodicReporter(Status.PeriodicStatusReporter):
    """
    This reporter creates an XML report of the status elements
    that are registered and sends them using an HTTP Post at
    the given interval.  Made to work with the P2P-Next lab.
    """
    def __init__(self, name, frequency, mypermid, error_handler=None):
        Status.PeriodicStatusReporter.__init__(self, name, frequency, error_handler=None)
        #self.logFile = open("ReporterLogFile.txt", "w")
        self.xmlLogs = []
        self.mypermid = mypermid

    host = "p2pnext-statistics.comp.lancs.ac.uk"
    path = "/post/"
    num_reports = 0
    
    def newElement(self, doc, name, value):
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

        if len(self.elements) == 0:
            return 
        
        # Create the report
        doc = xml.dom.minidom.Document()
        root = doc.createElement("nextsharedata")
        doc.appendChild(root)

        # Create the header
        header = doc.createElement("header")
        root.appendChild(header)
        header.appendChild(self.newElement(doc, "deviceid", self.mypermid))
        header.appendChild(self.newElement(doc, "timestamp", long(round(time.time()))))

        version = "ledbat_test_m23_trial_v_1_0"
        header.appendChild(self.newElement(doc, "swversion", version))

        # Now add the status elements
        report = doc.createElement("event")
        root.appendChild(report)

        report.appendChild(self.newElement(doc, "deviceid", self.mypermid))
        report.appendChild(self.newElement(doc, "swversion", version))
        report.appendChild(self.newElement(doc, "attribute", "statusreport"))
        report.appendChild(self.newElement(doc, "timestamp", long(round(time.time()))))
        for element in self.elements:
            report.appendChild(self.newElement(doc, element.get_name(), element.get_value()))

        # all done
        xml_printer = XmlPrinter.XmlPrinter(root)
        xml_str = xml_printer.to_pretty_xml()
        #xml_str = xml_printer.to_xml()
        #print xml_str

        # Now we send this to the service using a HTTP POST

        #self.logFile.write(xml_str + "\n")
        self.xmlLogs.append(xml_str)

    def post(self, xml_str):
        """
        Post a status report to the living lab using multipart/form-data
        This is a bit on the messy side, but it does work
        """

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
        
        h = httplib.HTTP(self.host)
        h.putrequest("POST", self.path)
        h.putheader("Host",self.host)
        h.putheader("User-Agent","NextShare status reporter 2009.4")
        h.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
        h.putheader("content-length",str(len(body)))
        h.endheaders()
        h.send(body)
        
        errcode, errmsg, headers = h.getreply()
        #print errcode, errmsg
        
        if errcode != 200:
            if self.error_handler:
                try:
                    self.error_handler(errcode, h.file.read())
                except Exception,e:
                    pass
    
    def stop(self, block=False):
        Status.PeriodicStatusReporter.stop(self, block)
        #self.logFile.close()
        
        for xml_str in self.xmlLogs:
            try:
                self.post(xml_str)
            except:
                pass

if __name__ == "__main__":
    """
    Small test routine to check an actual post (unittest checks locally)
    """

    status = Status.get_status_holder("UnitTest")
    def error_handler(code, message):
        print "Error:",code,message
    reporter = LivingLabPeriodicReporter("Living lab test reporter", 1.0, error_handler)
    status.add_reporter(reporter)
    s = status.create_status_element("TestString", "A test string")
    s.set_value("Hi from Njaal")

    time.sleep(2)

    print "Stopping reporter"
    reporter.stop()

    print "Sent %d reports"%reporter.num_reports
