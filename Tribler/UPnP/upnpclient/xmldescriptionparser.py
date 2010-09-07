# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""
This module implements parsing of UPnP Device Descriptions
and UPnP Service Descriptions.
"""
import xml.dom.minidom as minidom
import urlparse
import uuid

##############################################
#  PRIVATE UTILITY FUNCTIONS
##############################################

def _get_subelement_data(element, subelement_tagname):
    """Parse the data given an element and the tagName of an
    assumed subelement of that element."""
    subelement = _get_subelement(element, subelement_tagname)
    if not subelement : 
        return None
    else : 
        return _get_element_data(subelement)

def _get_subelement(element, subelement_tagname):
    """Get an element, given a parent element and a subelement tagname."""
    subelements = element.getElementsByTagName(subelement_tagname)
    if not subelements: 
        return None
    else : 
        return subelements[0]

def _get_element_data(element):
    """Parse the data of the given element."""
    text = ""
    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            text += node.data
        if node.nodeType == node.CDATA_SECTION_NODE:
            text += node.data
    return str(text)

def _get_absolute_url(base_url_string, url_string):
    """Construct absolute URL from an absolute base URL and a relative URL."""
    if base_url_string == None: 
        # Try to use only url_string
        if _is_absolute_url(url_string):
            return url_string
        else: return None
    else:
        return urlparse.urljoin(base_url_string, url_string)

def _is_absolute_url(url_string):
    """Determine whether given URL is absolute or not."""
    url = urlparse.urlparse(url_string)
    ret = True
    if url.scheme != "http": 
        ret = False
    if url.port == None: 
        ret = False
    if len(url.netloc) == 0 : 
        ret = False
    return ret



##############################################
#  PUBLIC PARSERS
##############################################

def parse_device_description(xml_description, base_url):
    """Parse device description. Return dictionary."""
    ddp = _DeviceDescriptionParser()
    return ddp.parse(xml_description, base_url)

def parse_service_description(xml_description):
    """Parse service description. Return dictionary."""
    sdp = _ServiceDescriptionParser()
    return sdp.parse(xml_description)

##############################################
#  DEVICE DESCRIPTION PARSER
##############################################

class _DeviceDescriptionParser:
    """
    This class implements parsing of the xml description of a 
    upnp device (rootdevice).
    
    Does not parse sub-devices.
    """
    def __init__(self):
        pass

    def parse(self, xmldata, base_url):
        """
        This method parses the xml description of a upnp device (rootdevice).
        -> Input is device description xml-data.
        <- Output is a dictionary with all relevant information.
        """
        try:
            doc = minidom.parseString(xmldata)
        except (TypeError, AttributeError):
            return None
        if doc == None: 
            return None

        root_elem = doc.documentElement
        device = {}

        # URLBase
        device['URLBase'] = _get_subelement_data(root_elem, 'URLBase')        
        if device['URLBase'] == None:
            device['URLBase'] = str(base_url)

        # Device Element
        device_elem = _get_subelement(root_elem, 'device')
        if not device_elem: 
            return None

        # deviceType
        data = _get_subelement_data(device_elem, "deviceType")
        if not data: 
            return None
        tokens = data.split(':')
        if len(tokens) == 5:
            device['deviceType'] = data
            device['deviceDomain'] = tokens[1]
            device['deviceTypeShort'] = tokens[3]
            device['deviceVersion'] = tokens[4]
        else : return None

        # UDN & UUID
        data = _get_subelement_data(device_elem, 'UDN') 
        if not data: 
            return None
        tokens = data.split(':')  # uuid:40a69722-4160-11df-9a88-00248116b859
        if len(tokens) == 2:
            device['UDN'] = data
            device['uuid'] = uuid.UUID(tokens[1])
        else: return None

        # Optional fields
        device['name'] = _get_subelement_data(device_elem, 
                                              'friendlyName')
        device['manufacturer'] = _get_subelement_data(device_elem, 
                                                      'manufacturer')
        device['manufacturerURL'] = _get_subelement_data(device_elem, 
                                                         'manufacturerURL')
        device['modelName'] = _get_subelement_data(device_elem, 
                                                   'modelName')
        device['modelDescription'] = _get_subelement_data(device_elem, 
                                                          'modelDescription')
        device['modelURL'] = _get_subelement_data(device_elem, 
                                                  'modelURL')
        device['serialNumber'] = _get_subelement_data(device_elem, 
                                                      'serialNumber')
        device['UPC'] = _get_subelement_data(device_elem, 'UPC')
        url_str = _get_subelement_data(device_elem, 'presentationURL')
        if url_str:
            device['presentationURL'] =  _get_absolute_url(device['URLBase'], 
                                                           url_str) 
        
        # Services
        device['services'] = []
        service_list_elem = _get_subelement(device_elem, 'serviceList')
        if service_list_elem:
            service_elems = service_list_elem.getElementsByTagName('service')
            for service_elem in service_elems:                
                data_str = {}
                data_str['serviceType'] = _get_subelement_data(service_elem, 
                                                               'serviceType')
                data_str['serviceId'] =  _get_subelement_data(service_elem, 
                                                              'serviceId')
                url_str =  _get_subelement_data(service_elem, 'SCPDURL')
                data_str['SCPDURL'] =  _get_absolute_url(device['URLBase'], 
                                                         url_str)
                url_str =  _get_subelement_data(service_elem, 'controlURL')
                data_str['controlURL'] = _get_absolute_url(device['URLBase'], 
                                                           url_str)
                url_str =  _get_subelement_data(service_elem, 'eventSubURL')
                data_str['eventSubURL'] = _get_absolute_url(device['URLBase'], 
                                                            url_str)
                device['services'].append(data_str)

        return device


##############################################
#  SERVICE  DESCRIPTION PARSER
##############################################

class _ServiceDescriptionParser:
    """
    This class implements parsing of the xml description of a 
    upnp service.
    """
    def __init__(self):
        pass

    def parse(self, xmldata):
        """
        This method parses the xml description of a upnp service.
        -> Input is device description xml-data.
        <- Output is a dictionary with all relevant information.
        """
        try:
            doc = minidom.parseString(xmldata)
        except (TypeError, AttributeError):
            return None
        if doc == None: 
            return None

        root_elem = doc.documentElement
        service = {}

        # State Variables
        service['stateVariables'] = []
        sv_table_elem =  _get_subelement(root_elem, 'serviceStateTable')
        sv_elems = sv_table_elem.getElementsByTagName('stateVariable')
        for sv_elem in sv_elems:
            stv = {}
            stv['name'] = _get_subelement_data(sv_elem, 'name')
            stv['dataType'] = _get_subelement_data(sv_elem, 'dataType')
            stv['defaultValue'] = _get_subelement_data(sv_elem, 'defaultValue')
            stv['sendEvents'] = sv_elem.attributes['sendEvents'].value
            service['stateVariables'].append(stv)

        # Actions
        service['actions'] = []
        action_table_elem = _get_subelement(root_elem, 'actionList')
        if action_table_elem:
            action_elems = action_table_elem.getElementsByTagName('action')
            for action_elem in action_elems:
                action = {}
                action['name'] = _get_subelement_data(action_elem, 'name')
                action['inargs'] = []
                action['outargs'] = []
                # Arguments
                arg_list_elem = _get_subelement(action_elem, 'argumentList')
                if arg_list_elem:
                    arg_elems = arg_list_elem.getElementsByTagName('argument')
                    for arg_elem in arg_elems:
                        arg = {}
                        arg['name'] = _get_subelement_data(arg_elem, 'name')
                        # Check that action_spec arguments refer to 
                        # defined state variables
                        rsv_name = _get_subelement_data(arg_elem, 
                                                        'relatedStateVariable')
                        for stv in service['stateVariables']:
                            if rsv_name == stv['name']: 
                                arg['rsv'] = rsv_name 
                                break
                        arg['direction'] = _get_subelement_data(arg_elem, 
                                                                'direction')
                        if arg['direction'] == 'in':
                            action['inargs'].append(arg)
                        elif arg['direction'] == 'out':
                            action['outargs'].append(arg)
                service['actions'].append(action)

        return service


##############################################
# MAIN
##############################################

if __name__ == '__main__':

    DEVICE_XML = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>http://193.156.106.130:44444/</URLBase>
<device>
<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
<friendlyName>Basic</friendlyName>
<manufacturer>Manufacturer</manufacturer>
<manufacturerURL>http://manufacturer.com</manufacturerURL>
<modelName>Model 1</modelName>
<modelDescription>Model description</modelDescription>
<modelURL>http://manufacturer.com/model_1</modelURL>
<serialNumber>123456</serialNumber>
<UDN>uuid:40a69722-4160-11df-9a88-00248116b859</UDN>
<UPC>012345678912</UPC>
<presentationURL>presentation.html</presentationURL>
<serviceList>
<service>
<serviceType>urn:schemas-upnp-org:service:SwitchPower:1</serviceType>
<serviceId>urn:upnp-org:serviceId:MySwitchPower</serviceId>
<SCPDURL>services/MySwitchPower/description.xml</SCPDURL>
<controlURL>services/MySwitchPower/control</controlURL>
<eventSubURL>services/MySwitchPower/events</eventSubURL>
</service>
</serviceList>
</device>
</root>
"""
    SERVICE_XML = """<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<actionList>
<action>
<name>SetTarget</name>
<argumentList>
<argument>
<name>NewTargetValue</name>
<relatedStateVariable>Status</relatedStateVariable>
<direction>in</direction>
</argument>
</argumentList>
</action>
<action>
<name>GetStatus</name>
<argumentList>
<argument>
<name>ResultStatus</name>
<relatedStateVariable>Status</relatedStateVariable>
<direction>out</direction>
</argument>
</argumentList>
</action>
<action>
<name>GetTarget</name>
<argumentList>
<argument>
<name>RetTargetValue</name>
<relatedStateVariable>Status</relatedStateVariable>
<direction>out</direction>
</argument>
</argumentList>
</action>
</actionList>
<serviceStateTable>
<stateVariable sendEvents="yes">
<name>Status</name>
<dataType>boolean</dataType>
<defaultValue>0</defaultValue>
</stateVariable>
</serviceStateTable>
</scpd>
"""

    print parse_device_description(DEVICE_XML, "http://vg.no/")

    print parse_service_description(SERVICE_XML)

