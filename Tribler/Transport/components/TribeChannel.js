// -*- coding: utf-8 -*-
// vi:si:et:sw=2:sts=2:ts=2
/*
  TribeChannel - Torrent video for <video>

  Written by Jan Gerber, Riccardo Petrocco
  see LICENSE.txt for license information
 */

Components.utils.import("resource://gre/modules/XPCOMUtils.jsm");

const Cc = Components.classes;
const Ci = Components.interfaces;

var tribeLoggingEnabled = true;

function LOG(aMsg) {
  if (tribeLoggingEnabled)
  {
    aMsg = ("*** Tribe : " + aMsg);
    Cc["@mozilla.org/consoleservice;1"].getService(Ci.nsIConsoleService).logStringMessage(aMsg);
    dump(aMsg);
  }
}


function TribeChannel() {
  this.wrappedJSObject = this;
  this.prefService = Cc["@mozilla.org/preferences-service;1"].getService(Ci.nsIPrefBranch).QueryInterface(Ci.nsIPrefService);
  try {
    tribeLoggingEnabled = this.prefService.getBoolPref("tribe.logging.enabled");
  } catch (e) {}

}

TribeChannel.prototype =
{
  classDescription: "Tribe channel",
  classID: Components.ID("68bfe8e9-c7ec-477d-a26c-2391333a7a24"),
  contractID: "@p2pnext.org/tribe/channel;1",
  QueryInterface: XPCOMUtils.generateQI([Ci.tribeIChannel,
                                         Ci.nsIChannel,
                                         Ci.nsISupports]),
  _xpcom_factory : TribeChannelFactory,
  init: false,
  backend: 'python',
  running: false,
  torrent_url: '',
  setTorrentUrl: function(url) {
    this.torrent_url = url;
    
    if (url.lastIndexOf('@')-url.lastIndexOf('/') == 41) // Format /root hash@xcontentdur
    	this.backend = 'swift';
    else
    	this.backend = 'python';
  },
  shutdown: function() {
    LOG("shutdown called\n"); 
    var msg = 'SHUTDOWN\r\n';
    this.outputStream.write(msg, msg.length);

    //this.outputStream.close();
    //this.inputStream.close();
    this.transport.close(Components.results.NS_OK);
  },
  asyncOpen: function(aListener, aContext)
  {
    var _this = this;
    if(this.init) {
      LOG('asyncOpen called again\n');
      throw Components.results.NS_ERROR_ALREADY_OPENED;
    }
    this.init = true;
    var socketTransportService = Cc["@mozilla.org/network/socket-transport-service;1"].getService(Ci.nsISocketTransportService);
    
    var hostIPAddr = "127.0.0.1";
    var hostPort = "62063"; // Arno, 2010-08-10: SwarmPlayer independent from SwarmPlugin
    if (this.backend == 'swift')
    	hostPort = "62481"; // dummy hack coexistence
    
    try {
      hostIPAddr = this.prefService.getCharPref("tribe.host.ipaddr");
    } catch (e) {}

    try {
      hostPort = this.prefService.getCharPref("tribe.host.port");
    } catch (e) {}

    this.transport = socketTransportService.createTransport(null, 0, hostIPAddr, hostPort, null);
    // Alright to open streams here as they are non-blocking by default
    this.outputStream = this.transport.openOutputStream(0,0,0);
    this.inputStream = this.transport.openInputStream(0,0,0);

	/* Arno, 2010-06-15: Let player inform BG process about capabilities
	   to allow sharing of BGprocess between SwarmTransport and SwarmPlugin
	   (the latter has pause capability)
	 */
    var msg = 'SUPPORTS VIDEVENT_START\r\n';
    msg = msg + 'START ' + this.torrent_url + '\r\n'; // concat, strange async interface
    this.outputStream.write(msg, msg.length);

    var dataListener = {
      onStartRequest: function(request, context) {},
      onStopRequest: function(request, context, status) {
      
        if(status == Components.results.NS_ERROR_CONNECTION_REFUSED) {
        	
          LOG("onStopRequest" + _this.running );
          if (_this.backend == 'swift' && _this.running == true)
        	  return;
          
          _this.startBackgroundDaemon();
          _this.init=false;
          _this.running=true;
          var timer = Cc["@mozilla.org/timer;1"].createInstance(Ci.nsITimer);
          timer.initWithCallback(function() { _this.asyncOpen(aListener, aContext) },
                                 1000, Ci.nsITimer.TYPE_ONE_SHOT);

          // swift backend
          if (_this.backend == 'swift')
          {
        	  // TODO: concurrency between swift starting and this HTTP req
	          var hashidx = _this.torrent_url.indexOf('/')+1;
	          var video_url = 'http://127.0.0.1:8080/' ;
	          video_url = video_url + _this.torrent_url.substr(hashidx,_this.torrent_url.length-hashidx);
	          this.onPlay(video_url);
          }
        }
        else 
        {
          LOG('BackgroundProcess closed Control connection\n');
          this.onBGError();
        }
      },
      onDataAvailable: function(request, context, inputStream, offset, count) {
        var sInputStream = Cc["@mozilla.org/scriptableinputstream;1"].createInstance(Ci.nsIScriptableInputStream);
        sInputStream.init(inputStream);

        var s = sInputStream.read(count).split('\r\n');
        
        for(var i=0;i<s.length;i++) {
          var cmd = s[i];
          if (cmd.substr(0,4) == 'PLAY') {
            var video_url = cmd.substr(5);
            this.onPlay(video_url);
            break;
          }
          if (cmd.substr(0,5) == "ERROR") {
            LOG('ERROR in BackgroundProcess\n');
            this.onBGError();
            break;
          }
        }
      },
      onBGError: function() {
            // Arno: It's hard to figure out how to throw an exception here
            // that causes FX to fail over to alternative <source> elements
            // inside the <video> element. The hack that appears to work is
            // to create a Channel to some URL that doesn't exist.
            //
            var fake_video_url = 'http://127.0.0.1:6877/createxpierror.html';
            var ios = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
            var video_channel = ios.newChannel(fake_video_url, null, null);
            video_channel.asyncOpen(aListener, aContext);
      },
      onPlay: function(video_url) {
          LOG('PLAY !!!!!! '+video_url+'\n');
          var ios = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
          var video_channel = ios.newChannel(video_url, null, null);
          video_channel.asyncOpen(aListener, aContext);
          //video_channel.onShutdown(_this.shutdown);
          //cleanup if window is closed
          var windowMediator = Cc["@mozilla.org/appshell/window-mediator;1"].getService(Ci.nsIWindowMediator);
          var nsWindow = windowMediator.getMostRecentWindow("navigator:browser");
          nsWindow.content.addEventListener("unload", function() { _this.shutdown() }, false);
      },
    };
    var pump = Cc["@mozilla.org/network/input-stream-pump;1"].createInstance(Ci.nsIInputStreamPump);
    pump.init(this.inputStream, -1, -1, 0, 0, false);
    pump.asyncRead(dataListener, null);
  },
  startBackgroundDaemon: function() {
    var osString = Cc["@mozilla.org/xre/app-info;1"]
                     .getService(Components.interfaces.nsIXULRuntime).OS;  
    var bgpath = "";
    if (this.backend == 'python')
    {
        if (osString == "WINNT")
            bgpath = 'SwarmEngine.exe';
        else if (osString == "Darwin")
            bgpath = "SwarmPlayer.app/Contents/MacOS/SwarmPlayer";
        else
            bgpath = 'swarmengined';

    }
    else
    {
	    // swift backend
        if (osString == "WINNT")
            bgpath = 'swift.exe';
        else if (osString == "Darwin")
            bgpath = "SwarmPlayer.app/Contents/MacOS/Swift"; // guess
        else
            bgpath = 'swift';
	    var urlarg = this.torrent_url.substr(0,this.torrent_url.indexOf('/'));
    }
   
    function runBackgroundDaemon(file) {

      // Arno, 2010-06-16: Doesn't work on Ubuntu with /usr/share/xul-ext* install      
      try {
          file.permissions = 0755;
      } catch (e) {}
      var process = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
      process.init(file);
      var args = [];
      if (this.backend == 'python')
      {
          if (tribeLoggingEnabled && osString != "Darwin")
            args.push('debug');
      }
      else
      {
	      // swift backend
	      args.push('-t');
	      args.push(urlarg);
	      args.push('-g');
	      args.push('0.0.0.0:8080');
	      args.push('-w');
	      // debugging on
	      //if (tribeLoggingEnabled && osString != "Darwin")
	      //{
	    //	  args.push('-D');
	    //	  args.push('log.log'); //dummy argument?
	     // }
      }
      process.run(false, args, args.length);
    }
    try {
      var em = Cc["@mozilla.org/extensions/manager;1"].getService(Ci.nsIExtensionManager);
      
      var file = em.getInstallLocation('tribe@p2pnext.org')
                   .getItemFile('tribe@p2pnext.org', 'bgprocess/'+bgpath);
      runBackgroundDaemon(file);
    } catch(e) {
      Components.utils.import("resource://gre/modules/AddonManager.jsm");
      AddonManager.getAddonByID('tribe@p2pnext.org', function(addon) {
        if (addon.hasResource('bgprocess')) {
          var resource = addon.getResourceURI('bgprocess');
          var file = resource.QueryInterface(Ci.nsIFileURL).file.QueryInterface(Ci.nsILocalFile);
          file.appendRelativePath(bgpath);
          runBackgroundDaemon(file);
        }
      });
    }
  },
} 

var TribeChannelFactory =
{
  createInstance: function (outer, iid)
  {
    if (outer != null)
      throw Components.results.NS_ERROR_NO_AGGREGATION;

    if (!iid.equals(Ci.tribeIChannel) &&
        !iid.equals(Ci.nsIChannel) &&
        !iid.equals(Ci.nsISupports) )
      throw Components.results.NS_ERROR_NO_INTERFACE;

    var tc =  new TribeChannel();
    var tcid = tc.QueryInterface(iid);
    return tcid;
  }
};

function NSGetModule(compMgr, fileSpec) {
  return XPCOMUtils.generateModule([TribeChannel]);
}

