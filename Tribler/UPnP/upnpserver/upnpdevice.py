# Written by Ingar Arntzen, Norut
# see LICENSE.txt for license information

"""
This module implements a UPnP device.  The implementation
takes care of automatic production of xml and html descriptions
of the device.
"""
import uuid
import exceptions

#
# HTML
#

_HTML_FMT = "<html>\n<header></header>\n<body>\n%s</body>\n</html>"
_HTML_BODY_FMT = "<h1>RootDevice : %s</h1>\n%s"
_HTML_SERVICE_LIST_FMT = "<h2>Services</h2><ol>\n%s</ol>\n"

_HTML_DEVICE_TYPE_FMT = "DeviceType : urn:%s:device:%s:%s<br>\n"
_HTML_DEVICE_NAME_FMT = "Name : %s<br>\n"
_HTML_MANUFACTURER_FMT = "Manufacturer : %s<br>\n"
_HTML_MANUFACTURER_URL_FMT = "ManufacturerURL : %s<br>\n"
_HTML_MODEL_NAME_FMT = "ModelName : %s<br>\n"
_HTML_MODEL_NUMBER_FMT = "ModelNumber : %s<br>\n"
_HTML_MODEL_DESCRIPTION_FMT = "ModelDescription : %s<br>\n"
_HTML_MODEL_URL_FMT = "ModelURL : %s<br>\n"
_HTML_SERIAL_NUMBER_FMT = "SerialNumber : %s<br>\n"
_HTML_DEVICE_UUID_FMT = "UDN : uuid:%s<br>\n"
_HTML_UPC_FMT = "UPC : %s<br>\n"
_HTML_PRESENTATION_FMT = "PresentationURL : <a href=%s>%s</a><br>\n"
_HTML_DESCRIPTION_FMT = "DescriptionURL : <a href=%s>%s</a><br>\n"

_HTML_SERVICE_FMT = "<li><h3>%s</h3><br>\n%s</li>\n"
_HTML_SERVICE_TYPE_FMT = "ServiceType : urn:schemas-upnp-org:" + \
    "service:%s:%s<br>\n"
_HTML_SERVICE_ID_FMT = "ServiceID : urn:upnp-org:serviceId:%s<br>\n"
_HTML_SERVICE_DESCRIPTION_URL_FMT = "SCPDURL : <a href=%s>%s</a><br>\n"
_HTML_SERVICE_CONTROL_URL_FMT = "ControlURL : %s<br>\n"
_HTML_SERVICE_EVENT_URL_FMT = "EventSubURL : %s<br>\n"


def _device_entries_tohtml(device):
    """Produce html for all attributes of a device."""
    str_ = []
    str_.append(_HTML_DEVICE_TYPE_FMT % (device.device_domain,
               device.device_type,
                                       device.device_version))
    str_.append(_HTML_DEVICE_NAME_FMT % device.name)
    if device.manufacturer != None:
        str_.append(_HTML_MANUFACTURER_FMT % device.manufacturer)
    if device.manufacturer_url != None:
        str_.append(_HTML_MANUFACTURER_URL_FMT % device.manufacturer_url)
    if device.model_name != None:
        str_.append(_HTML_MODEL_NAME_FMT % device.model_name)
    if device.model_number != None:
        str_.append(_HTML_MODEL_NUMBER_FMT % device.model_number)
    if device.model_description != None:
        str_.append(_HTML_MODEL_DESCRIPTION_FMT % device.model_description)
    if device.model_url != None:
        str_.append(_HTML_MODEL_URL_FMT % device.model_url)
    if device.serial_number != None:
        str_.append(_HTML_SERIAL_NUMBER_FMT % device.serial_number)
    str_.append(_HTML_DEVICE_UUID_FMT % device.uuid)
    if device.upc != None:
        str_.append(_HTML_UPC_FMT % device.upc)
    url = device.get_presentation_url()
    str_.append(_HTML_PRESENTATION_FMT % (url, url))
    url = device.get_description_url()
    str_.append(_HTML_DESCRIPTION_FMT % (url, url))
    return "".join(str_)


def _service_list_tohtml(services):
    """Produce html for all services contained in a device."""
    if len(services) > 0:
        list_ = []
        for service in services:
            str_ = ""
            str_ += _HTML_SERVICE_TYPE_FMT % (service.service_type,
                                           service.service_version)
            str_ += _HTML_SERVICE_ID_FMT % service.service_id
            url = service.base_url + service.description_path
            str_ += _HTML_SERVICE_DESCRIPTION_URL_FMT % (url, url)
            str_ += _HTML_SERVICE_CONTROL_URL_FMT % \
                (service.base_url + service.control_path)
            str_ += _HTML_SERVICE_EVENT_URL_FMT % \
                (service.base_url + service.event_path)
            list_.append(_HTML_SERVICE_FMT % (service.service_id, str_))
        return _HTML_SERVICE_LIST_FMT % "".join(list_)
    else:
        return ""


def _device_tohtml(device):
    """Produce html description for a device. """
    entries = _device_entries_tohtml(device)
    service_list = _service_list_tohtml(device.get_services())
    body = _HTML_BODY_FMT % (device.name, entries + service_list)
    return _HTML_FMT % body


#
# XML
#

_DEVICE_DESCRIPTION_FMT = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>%s</URLBase>
%s
</root>"""

_DEVICE_FMT = "<device>\n%s</device>"
_DEVICE_LIST_FMT = "<deviceList>\n%s</deviceList>\n"
_SERVICE_LIST_FMT = "<serviceList>\n%s</serviceList>\n"

_DEVICE_TYPE_FMT = "<deviceType>urn:%s:device:%s:%s</deviceType>\n"
_DEVICE_NAME_FMT = "<friendlyName>%s</friendlyName>\n"
_MANUFACTURER_FMT = "<manufacturer>%s</manufacturer>\n"
_MANUFACTURER_URL_FMT = "<manufacturerURL>%s</manufacturerURL>\n"
_MODEL_NAME_FMT = "<modelName>%s</modelName>\n"
_MODEL_NUMBER_FMT = "<modelNumber>%s</modelNumber>\n"
_MODEL_DESCRIPTION_FMT = "<modelDescription>%s</modelDescription>\n"
_MODEL_URL_FMT = "<modelURL>%s</modelURL>\n"
_SERIAL_NUMBER_FMT = "<serialNumber>%s</serialNumber>\n"
_DEVICE_UUID_FMT = "<UDN>uuid:%s</UDN>\n"
_UPC_FMT = "<UPC>%s</UPC>\n"
_PRESENTATION_FMT = "<presentationURL>%s</presentationURL>\n"


_SERVICE_FMT = "<service>\n%s</service>\n"
_SERVICE_TYPE_FMT = "<serviceType>urn:schemas-upnp-org:service:" + \
    "%s:%s</serviceType>\n"
_SERVICE_ID_FMT = "<serviceId>urn:upnp-org:serviceId:%s</serviceId>\n"
_SERVICE_DESCRIPTION_URL_FMT = "<SCPDURL>%s</SCPDURL>\n"
_SERVICE_CONTROL_URL_FMT = "<controlURL>%s</controlURL>\n"
_SERVICE_EVENT_URL_FMT = "<eventSubURL>%s</eventSubURL>\n"


def _device_entries_toxml(device):
    """Produce xml description for device attributes."""
    str_ = []
    str_.append(_DEVICE_TYPE_FMT % (device.device_domain,
                                  device.device_type, device.device_version))
    str_.append(_DEVICE_NAME_FMT % device.name)
    if device.manufacturer != None:
        str_.append(_MANUFACTURER_FMT % device.manufacturer)
    if device.manufacturer_url != None:
        str_.append(_MANUFACTURER_URL_FMT % device.manufacturer_url)
    if device.model_name != None:
        str_.append(_MODEL_NAME_FMT % device.model_name)
    if device.model_number != None:
        str_.append(_MODEL_NUMBER_FMT % device.model_number)
    if device.model_description != None:
        str_.append(_MODEL_DESCRIPTION_FMT % device.model_description)
    if device.model_url != None:
        str_.append(_MODEL_URL_FMT % device.model_url)
    if device.serial_number != None:
        str_.append(_SERIAL_NUMBER_FMT % device.serial_number)
    str_.append(_DEVICE_UUID_FMT % device.uuid)
    if device.upc != None:
        str_.append(_UPC_FMT % device.upc)
    str_.append(_PRESENTATION_FMT % (device.get_presentation_url()))
    return "".join(str_)


def _device_list_toxml(devices):
    """Produce xml for devices contained within a device."""
    if len(devices) > 0:
        str_ = ""
        for device in devices:
            str_ += device.to_xml()
        return _DEVICE_LIST_FMT % str_
    else:
        return ""


def _service_list_toxml(services):
    """Produce xml for services contained within a device."""
    if len(services) > 0:
        list_ = []
        for service in services:
            str_ = ""
            str_ += _SERVICE_TYPE_FMT % (service.service_type,
                                      service.service_version)
            str_ += _SERVICE_ID_FMT % service.service_id
            str_ += _SERVICE_DESCRIPTION_URL_FMT % (service.description_path)
            str_ += _SERVICE_CONTROL_URL_FMT % (service.control_path)
            str_ += _SERVICE_EVENT_URL_FMT % (service.event_path)
            list_.append(_SERVICE_FMT % str_)
        return _SERVICE_LIST_FMT % "".join(list_)
    else:
        return ""


#
# UPNP DEVICE
#

class UPnPDeviceError(exceptions.Exception):

    """Errro associated with UPnP Device."""
    pass


class UPnPDevice:

    """
    This implements the internal representation of a UPNP Device.
    The representation is used to generate the XML description,
    and to add or remove services.
    The given service manager implements the hierarchical namespace
    for devices and services.
    """

    def __init__(self, device_config=None):
        self._sm = None
        self._is_root = False

        # Initialse Device from config.
        if device_config == None:
            device_config = {}
        self.name = device_config.get('name', None)
        self.device_type = device_config.get('device_type', None)
        self.device_version = device_config.get('device_version', 1)
        self.device_domain = device_config.get('device_domain',
                                               'schemas-upnp-org')
        self.manufacturer = device_config.get('manufacturer', None)
        self.manufacturer_url = device_config.get('manufacturer_url', None)
        self.model_name = device_config.get('model_name', None)
        self.model_number = device_config.get('model_number', None)
        self.model_description = device_config.get('model_description', None)
        self.model_url = device_config.get('model_url', None)
        self.serial_number = device_config.get('serial_number', None)
        self.uuid = uuid.uuid1()
        self.upc = device_config.get('upc', None)

        self.base_url = ""
        self.presentation_path = ""
        self.description_path = ""

    def set_service_manager(self, service_manager):
        """Initialise device with reference to service manager."""
        self._sm = service_manager
        self.base_url = self._sm.get_base_url()
        self.presentation_path = "devices/%s/presentation.html" % self.name
        self.description_path = "devices/%s/description.xml" % self.name

    def set_is_root(self, value):
        """Initialise device with is_root flag."""
        self._is_root = value

    def is_root(self):
        """Checks if device is root."""
        return self._is_root

    def is_valid(self):
        """Checks if device object has been properly initialised."""
        return (self.device_type != None and self.name != None
                and self.uuid != None and self.base_url != None
                and self._sm != None)

    def get_services(self):
        """Returns services which are included in this device."""
        return self._sm.get_services_of_device(self)

    def get_devices(self):
        """Returns devices which are included in this device."""
        return self._sm.get_devices_of_device(self)

    def to_xml(self):
        """Returns the xml description of this device."""
        if self.is_valid():
            device_entries_xml = _device_entries_toxml(self)
            service_list_xml = _service_list_toxml(self.get_services())
            device_list_xml = _device_list_toxml(self.get_devices())
            return _DEVICE_FMT % (device_entries_xml +
                                 service_list_xml + device_list_xml)
        else:
            msg = "Can not generate XML description . Invalid Device"
            raise UPnPDeviceError(msg)

    def get_presentation_url(self):
        """Returns the presentation URL (html) for this device."""
        if self.is_root():
            return self._sm.get_presentation_path()
        else:
            return self.base_url + self.presentation_path

    def get_description_url(self):
        """Returns the description URL (xml) for this device."""
        if self.is_root():
            return self._sm.get_description_path()
        else:
            return self.base_url + self.description_path

    def get_xml_description(self):
        """
        Returns xml description wrapped in a valid xml document.
        Should only be invoked on the root device.
        """
        if self.is_valid():
            return _DEVICE_DESCRIPTION_FMT % (self.base_url, self.to_xml())
        else:
            msg = "Can not generate XML description. Invalid Device"
            raise UPnPDeviceError(msg)

    def get_html_description(self):
        """Return html description of device."""
        return _device_tohtml(self)

    def close(self):
        """Close this device."""
        pass

#
# MAIN
#

if __name__ == '__main__':

    DEVICE_CONF = {
        'device_type': "MediaServer",
        'device_version': 1,
        'device_domain': 'schemas-upnp-org',
        'name': "MediaServer",
        'manufacturer': "Manufacturer",
        'manufacturer_url': 'http://manufacturer.com',
        'model_description': 'Model description',
        'model_name': 'Model 1',
        'model_number': '123456',
        'model_url': 'http://manufacturer.com/model_1',
        'serial_number': '123456',
        'uuid': "3dd705c2-1c8a-11df-80c7-00248116b859",
        'upc': 'universial product code',
    }

    class MockService:

        """Mock Service"""
        def __init__(self):
            self.service_type = "ContentDirectory"
            self.service_version = 1
            self.service_id = "ContentDirectory"
            self.description_path = "%s/description.xml" % self.service_id
            self.control_path = "%s/control" % self.service_id
            self.event_path = "%s/events" % self.service_id
            self.base_url = "http://myhost:4444/"

    class MockServiceManager:

        """Mock Service Manager."""
        def __init__(self):
            self._mock_service = MockService()

        def get_services_of_device(self, device):
            """Mock method."""
            return [self._mock_service]

        def get_devices_of_device(self, device):
            """Mock method."""
            return []

        def get_base_url(self):
            """Mock method."""
            return 'http://myhost:4444/'

    SM = MockServiceManager()

    DEVICE = UPnPDevice(DEVICE_CONF)
    DEVICE.set_service_manager(SM)

    print DEVICE.get_xml_description()
    print DEVICE.get_html_description()
