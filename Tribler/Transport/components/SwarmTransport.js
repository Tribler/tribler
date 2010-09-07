// -*- coding: utf-8 -*-
// vi:si:et:sw=2:sts=2:ts=2
/*
  JavaScript global constructor swarmTransport
  
  Written by Jan Gerber
  see LICENSE.txt for license information
 */

Components.utils.import("resource://gre/modules/XPCOMUtils.jsm");

const Cc = Components.classes;
const Ci = Components.interfaces;

function SwarmTransport() {
}

SwarmTransport.prototype =
{
  classDescription: "swarmTransport",
  classID: Components.ID("3dfea7b2-52e6-467f-b2c6-19fd6d4596bf"),
  contractID: "@p2pnext.org/tribe/swarmTransport;1",
  QueryInterface: XPCOMUtils.generateQI(
    [Ci.tribeISwarmTransport,
     Ci.nsISecurityCheckedComponent,
     Ci.nsISupportsWeakReference,
     Ci.nsIClassInfo]),
  _xpcom_factory : SwarmTransportFactory,
  _xpcom_categories : [{
    category: "JavaScript global constructor",
    entry: "swarmTransport"
  }],
  version: 0.1,
} 

var SwarmTransportFactory =
{
  createInstance: function (outer, iid)
  {
    if (outer != null)
      throw Components.results.NS_ERROR_NO_AGGREGATION;

    if (!iid.equals(Ci.nsIProtocolHandler) &&
        !iid.equals(Ci.nsISupports) )
      throw Components.results.NS_ERROR_NO_INTERFACE;

    return (new SwarmTransport()).QueryInterface(iid);
  }
};

function NSGetModule(compMgr, fileSpec) {
  return XPCOMUtils.generateModule([SwarmTransport]);
}

