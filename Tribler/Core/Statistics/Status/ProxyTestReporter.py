import time
import sys

import httplib

import XmlPrinter
import xml.dom.minidom

import Status
from Tribler.Core.Utilities.utilities import show_permid_short

from LivingLabReporter import LivingLabPeriodicReporter


class ProxyTestPeriodicReporter(LivingLabPeriodicReporter):
    host = "proxytestreporter.tribler.org"
    path = "/postV2.py"

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
        header.appendChild(self.new_element(doc, "timestamp", long(round(time.time()))))

        # ProxyService 90s Test_
#        try:
#            from Tribler.Core.Session import Session
#            session = Session.get_instance()
#            if session.lm.overlay_apps.proxy_peer_manager.connectable:
#                    connectable = 1
#            else:
#                    connectable = 0
#
#            start_time = long(round(session.start_time))
#
#            my_permid = show_permid_short(session.get_permid())
#        except Exception,e:
#            connectable = 0
#            start_time = 0
#            my_permid = 0
#
#        header.appendChild(self.new_element(doc, "connectable", connectable))
#        header.appendChild(self.new_element(doc, "startuptime", start_time))
#        header.appendChild(self.new_element(doc, "clientpermid", my_permid))
        # _ProxyService 90s Test

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
                    print(element.__class__)
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
            return  # Was nothing here for us

        # all done
        xml_printer = XmlPrinter.XmlPrinter(root)
        if self.print_post:
            print(xml_printer.to_pretty_xml(), file=sys.stderr)
        xml_str = xml_printer.to_xml()

        # Now we send this to the service using a HTTP POST
        self.post(xml_str)

# if __name__ == "__main__":
#    from Tribler.Core.Statistics.Status.Status import get_status_holder

#    status = get_status_holder("ProxyTest")
#    status.add_reporter(ProxyTestPeriodicReporter("Test", 5, "test-id"))
#    status.create_and_add_event("foo", ["foo", "bar"])
#    status.create_and_add_event("animals", ["bunnies", "kitties", "doggies"])
#    status.create_and_add_event("numbers", range(255))

#    import time
#    time.sleep(15)
