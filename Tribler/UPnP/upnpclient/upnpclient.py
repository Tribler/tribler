# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""UPnP Client (Control Point).""" 


import urlparse
import Tribler.UPnP.ssdp.ssdpclient as ssdpclient
import Tribler.UPnP.common.asynchHTTPclient as httpclient
import xmldescriptionparser as xmlparser
import upnpservicestub
import httpserver

_HTTP_GET_REQUEST_FMT = """GET %s HTTP/1.1\r
HOST: %s:%s\r
ContentLength: 0\r\n\r\n"""

_HTTP_200_RESPONSE = "HTTP/1.1 200 OK"

_LOG_TAG = "UPnPClient"

class _Logger:
    """Internal Logger presented to internal modules."""
    def __init__(self, logger):
        self._logger = logger
    def log(self, log_tag, msg):
        """
        UPnPClient logtag is atted to log info from 
        internal modules."""
        if self._logger:
            self._logger.log(_LOG_TAG, log_tag, msg)

##############################################
# SERVICE STUB CACHE
##############################################

class ServiceStubCache:

    """
    A ServiceStub is uniquely defined by device_uuid and
    service_id. This cash holds a list of unique service stub instances. 
    """

    def __init__(self):
        self._stubs = []

    def exists(self, device_uuid, service_id):
        """Returns true if given stub identified by device_uuid and service_id
        is available in the cache."""
        return True if self._get_index(device_uuid, service_id) > -1 else False

    def lookup(self, device_uuid, service_id):
        """Lookup ServiceStub in Cache."""
        index = self._get_index(device_uuid, service_id)
        if index == None:
            return None
        else:
            return self._stubs[index]

    def insert(self, stub):
        """
        Insert Service Stub in place if Service Stub 
        already exists in cache.
        """
        index = self._get_index(stub.get_device_uuid(), stub.get_service_id())
        if index == None:
            self._stubs.append(stub)
        else:
            self._stubs.remove(index)
            self._stubs.insert(index, stub)

    def remove(self, device_uuid, service_id):
        """Remove Service Stub from cache."""
        index = self._get_index(device_uuid, service_id)
        if index != None:
            self._stubs.remove(index)

    def _get_index(self, device_uuid, service_id):
        """
        Get the index of Service Stub with matching 
        device_uuid and service_id.
        If none exists return None. Else return index.
        """
        for i in range(len(self._stubs)):
            if self._stubs[i].get_device_uuid() != device_uuid: 
                continue
            if self._stubs[i].get_service_id() != service_id: 
                continue
            return i
        return None
            


##############################################
# UPNP CLIENT
##############################################

class UPnPClient:
    
    """UPnP Client (Control Point) keeps an update view of the local network,
    in terms of visible UPnP devices and services. UPnP client also provides 
    stub implementeation for remote services, through which actions and events
    are communicated."""
    
    def __init__(self, task_runner, logger=None):

        # Logging
        self.logger = _Logger(logger)

        # Task Runner
        self.task_runner = task_runner

        # HTTP Server
        self._https = httpserver.HTTPServer(self, task_runner, 
                                            logger=self.logger)

        # SSDP Client
        self._ssdpc = ssdpclient.SSDPClient(task_runner, logger=self.logger)
        self._ssdpc.set_add_handler(self._handle_ssdpc_add_device)
        self._ssdpc.set_remove_handler(self._handle_ssdpc_remove_device)

        # Non-blocking HTTP Client
        self._asynch_httpc = httpclient.AsynchHTTPClient(task_runner)

        # Blocking HTTP Client
        self.synch_httpc = httpclient.SynchHTTPClient(self._asynch_httpc)

        # Pending Non-blocking HTTP Requests
        self._pending = {} # rid: uuid

        # UPnPDevice Specifications
        self._device_map = {} # uuid:{}

        # Service Stubs (cache)
        self._stub_cache = ServiceStubCache()

        # Startup by TaskRunner
        self.task_runner.add_task(self.startup)
    
    def startup(self):
        """Startup UPnP Client, by starting internal modules http server and
        ssdpclient."""
        self._https.startup()
        self._ssdpc.startup()

    def search(self):
        """Submit a new search for devices. Non-blocking."""
        self.task_runner.add_task(self._ssdpc.search)
        
    ##############################################
    # PUBLIC API
    ##############################################

    def get_base_event_url(self):
        """Get URL where notifications from remote services will be accepted."""
        return self._https.get_base_event_url()

    def get_device_uuids(self):
        """Get uuids of all known devices."""
        return self._device_map.keys()

    def get_service_types(self):
        """Get list of unique service types of live services discovered by the 
        UPnPClient."""
        list_ = []
        for d_uuid, s_id, s_type in self._get_all_services():
            if not s_type in list_:
                list_.append(s_type)
        return list_

    def get_service_ids(self):
        """Get all service ids of live services discovered by the UPnPClient."""
        list_ = []
        for d_uuid, s_id, s_type in self._get_all_services():
            if not s_id in list_:
                list_.append(s_id)
        return list_
    
    def get_device(self, uuid):
        """Given uuid.UUID return device representation (dictionary) - 
        if such a device has been discovered."""
        return self._device_map.get(uuid, None)

    def get_services_by_type(self, service_type):
        """Get all service stubs of live services, given service type."""
        # TODO : By using the non-blocking HTTPClient the
        # underlying http requests could be made in paralell.
        stub_list = []
        for d_uuid, s_id, s_type in self._get_all_services():
            if s_type == service_type:
                stub = self._get_service_stub(d_uuid, s_id)
                if stub:
                    stub_list.append(stub)
        return stub_list
            
    def get_services_by_short_id(self, short_service_id):
        """Get all service stubs of live services, given short service id."""
        service_id = "urn:upnp-org:serviceId:" + short_service_id
        return  self.get_services_by_id(service_id)

    def get_services_by_id(self, service_id):
        """Get all service stubs of live services, given service id."""
        # TODO : By using the non-blocking HTTPClient the
        # underlying http requests could be made in paralell.
        # Alternatively, do the common thing first and then only
        # if that fails, do the uncommon thing.
        stub_list = []
        for d_uuid, s_id, s_type in self._get_all_services():
            if s_id == service_id:
                stub = self._get_service_stub(d_uuid, s_id)
                if stub:
                    stub_list.append(stub)
        return stub_list

    def get_service(self, device_uuid, service_id):
        """Get service stub uniquely defined by device_uuid 
        (uuid.UUID) and full service_id"""
        return self._get_service_stub(device_uuid, service_id)

    def close(self):
        """Close UPnPClient."""
        self._https.close()
        self._ssdpc.close()
        self._asynch_httpc.close()


    ##############################################
    # PRIVATE UTILITY
    ##############################################

    def _get_all_services(self):
        """Return all services know to UPnPClient. Return tuples of
        device_uuid, service_id, service_type."""
        tuples = []
        for device in self._device_map.values():            
            for service in device['services']:
                tuples.append((device['uuid'], service['serviceId'], 
                               service['serviceType']))
        return tuples

    def _get_cached_stub(self, device_uuid, service_id):
        """Get service stub instance from cache."""
        # Check Device Map
        if not self._device_map.has_key(device_uuid):
            return None
        # Check Cache
        return self._stub_cache.lookup(device_uuid, service_id)

    def _get_device_and_service(self, device_uuid, service_id):
        """Get device description (dictionary) and service description
        (dictionary)."""
        # Check Device Map
        if not self._device_map.has_key(device_uuid):
            return None, None
        # Check if Device has Service with given service_id
        service = None
        device = self._device_map[device_uuid]
        for service_dict in device['services']:
            if service_dict['serviceId'] == service_id:
                service = service_dict
                break
        return device, service
        
    def _get_service_stub(self, device_uuid, service_id):
        """Get service stub. If necessary, download service
        description, parse it and instantiate service stub."""
        # Check Cache
        stub = self._get_cached_stub(device_uuid, service_id)
        if stub != None:
            return stub

        # Get device description and service description from device description
        device, service = self._get_device_and_service(device_uuid, service_id)
        if service == None:
            return None

        # Fetch Service Description and build ServiceStub (Blocking)
        url = urlparse.urlparse(service['SCPDURL'])
        http_request = _HTTP_GET_REQUEST_FMT % (url.path, 
                                                url.hostname, url.port)
        status, reply = self.synch_httpc.request(url.hostname, 
                                                  url.port, http_request)
        xml_data = ""
        if status == httpclient.SynchHTTPClient.OK:
            header, xml_data = reply
            if not header[:len(_HTTP_200_RESPONSE)] == _HTTP_200_RESPONSE:
                return None
        elif status == httpclient.SynchHTTPClient.FAIL:
            return None

        # Parse XML Data.
        service_spec = xmlparser.parse_service_description(xml_data)

        # Create Service Stub
        stub = upnpservicestub.UPnPServiceStub(self, device, 
                                               service, service_spec)
        self._stub_cache.insert(stub)
        return stub


    ##############################################
    # PRIVATE HANDLERS
    ##############################################

    def _handle_ssdpc_add_device(self, uuid, location):
        """A new device has been added by the SSDP client."""
         # Check Location
        url = urlparse.urlparse(location)
        if (url.hostname == None): 
            return
        if (url.port == None): 
            return        
        # Dispatch Request Device Description
        # The UPnP specification specifies that path is sent
        # in the first line of the request header, as opposed 
        # to the full location. Still, at least one 3'rd party 
        # implementation expects the full location. Therefore 
        # we send two requests to be sure. 
        # TODO: only send the second if the first fails.
        request_1 = _HTTP_GET_REQUEST_FMT % (url.path, url.hostname, url.port)
        request_2 = _HTTP_GET_REQUEST_FMT % (location, url.hostname, url.port)
        rid_1 = self._asynch_httpc.get_request_id()
        rid_2 = self._asynch_httpc.get_request_id()

        self._asynch_httpc.request(rid_1, url.hostname, url.port, 
                                   request_1, self._handle_httpc_abort, 
                                   self._handle_httpc_response)
        self._asynch_httpc.request(rid_2, url.hostname, url.port, 
                                   request_2, self._handle_httpc_abort, 
                                   self._handle_httpc_response)

        # Pending
        self._pending[rid_1] = (uuid, location)
        self._pending[rid_2] = (uuid, location)

    def _handle_ssdpc_remove_device(self, uuid):
        """A device has been removed by the SSDP."""
       # Check if a request happens to be pending
        found_rids = []
        for rid, (uuid_, loc) in self._pending.items():
            if uuid_ == uuid: 
                found_rids.append(rid)
        if found_rids:
            for rid in found_rids:
                del self._pending[rid]
        # Remove from deviceMap
        if self._device_map.has_key(uuid):
            del self._device_map[uuid]

    def _handle_httpc_response(self, rid, header, body):
        """A http response is received by the 
        asynchronous http client."""
        uuid, location = self._pending[rid]
        del self._pending[rid]

        if self._device_map.has_key(uuid):
            # Second response
            return

        # Check 200 OK
        if header[:len(_HTTP_200_RESPONSE)] == _HTTP_200_RESPONSE:
            device = xmlparser.parse_device_description(body, location)
            # Check that announce uuid matches uuid from device description
            if (uuid == device['uuid']):        
                self._device_map[uuid] = device

    def _handle_httpc_abort(self, rid, error, msg):
        """The asynchronous http client reports the abort of a http request. """
        del self._pending[rid]

    def handle_notification(self, device_uuid, service_id, sid, seq, var_list):
        """Httpserver delivers an event notification. UPnP delegates it to
        the appropriate stub."""
        stub = self._get_cached_stub(device_uuid, service_id)
        stub.notify(sid, seq, var_list)

##############################################
# MAIN
##############################################

if __name__ == "__main__":

    import Tribler.UPnP.common.upnplogger as upnplogger
    LOGGER = upnplogger.get_logger()
    
    import Tribler.UPnP.common.taskrunner as taskrunner
    TR = taskrunner.TaskRunner()
    CLIENT = UPnPClient(TR, logger=LOGGER)
    
    import threading
    import time
    import exceptions
    import traceback

    def test_reflection(client):
        """Test reflection-like api."""
        for uuid in client.get_all_device_uuids():
            print client.get_device(uuid)
        print client.get_all_service_types()
        print client.get_all_service_ids()

    def test_service_id(client):
        """Test service_id api."""
        list_ = []
        list_ += client.get_services_by_short_id("URLService")
        list_ += client.get_services_by_short_id("MySwitchPower")
        list_ += client.get_services_by_short_id("Dimming:1")
        list_ += client.get_services_by_short_id("SwitchPower:1")
        return list_

    def test_service_type(client):
        """Test service_type api."""
        list_ = []
        type_1 = "urn:schemas-upnp-org:service:URLService:1"
        type_2 = "urn:schemas-upnp-org:service:SwitchPower:1"
        type_3 = "urn:schemas-upnp-org:service:Dimming:1"
        list_ += client.get_services_by_type(type_1)
        list_ += client.get_services_by_type(type_2)
        list_ += client.get_services_by_type(type_3)
        return list_

    def print_stub_list(list_):
        """Print the given list of stubs."""
        for stub in list_:
            for sv_name in stub.get_sv_names():
                print stub.get_sv_def(sv_name)
            for action_name in stub.get_action_names():
                print stub.get_action_def(action_name)

    def event_handler(sv_name, seq, obj):
        """Simple event handler."""
        LOGGER.log("TEST", "", "Event %s %d %s" % (sv_name, seq, str(obj)))

    def test_swp_action(client):
        """Test SwitchPower action api."""
        services = client.get_services_by_short_id("MySwitchPower")
        #services = client.get_services_by_short_id("SwitchPower:1")
        if not services: 
            return
        swp_service = services[0]

        swp_service.subscribe(event_handler)
        swp_service.renew()
        swp_service.action("SetTarget", [True])
        swp_service.action("GetStatus")
        swp_service.unsubscribe(event_handler)

    class Test:
        """Tester."""
        def __init__(self, client):
            self.client = client

        def run(self):
            """Run testeer."""
            LOGGER.log("TEST", "", "Start")
            time.sleep(4)
            #test_reflection(self.client)
            #stub_list = test_service_id(self.client)
            #stub_list = test_service_type(self.client)
            #print_stub_list(stub_list)
            test_swp_action(self.client)
            time.sleep(4)
            LOGGER.log("TEST", "", "Stop")


    TEST = Test(CLIENT)
    THREAD = threading.Thread(target=TEST.run)
    THREAD.setDaemon(True)
    THREAD.start()
    try:
        TR.run_forever()
    except KeyboardInterrupt, w:
        print
    except exceptions.Exception, e:
        traceback.print_exc()
    CLIENT.close()
    TR.stop()
    THREAD.join()

