/*
 *	Written by Riccardo Petrocco
 *	see LICENSE.txt for license information
 * 
 */


function TribeInterface( controller )
{
	this.initialize( controller );
	return this;
}

TribeInterface.prototype =
{
	/*
	 * Constructor
	 */
	initialize: function(controller) {
		this._controller = controller;
		this._error = '';
		this._token = '';
		this._report  = true;
	},

	/*
	 * Error handle
	 */
	ajaxError: function(request, error_string, exception, ajaxObject) {
		var token;
		remote = this;

		remote._error = request.responseText
					? request.responseText.trim().replace(/(<([^>]+)>)/ig,"")
					: "";
		if( !remote._error.length )
			remote._error = 'Server not responding';
		
        if (remote._report) {
    		alert(remote._error);
		
		    this._controller._BPClosed = true;
		    remote._report = false
	    }
		    
	},

	sendRequest: function( data, success, async ) {

		remote = this;
		if( typeof async != 'boolean' )
		  async = true;

		var ajaxSettings = {
			url: 'webUI',
			type: 'GET',
			contentType: 'json',
			dataType: 'json',
			cache: false,
			data: $.toJSON(data),
			error: function(request, error_string, exception){ remote.ajaxError(request, error_string, exception, ajaxSettings); },
			success: success,
			async: async
		};

		$.ajax( ajaxSettings );
	},

    // TODO not used now
	loadStats: function( callback, async ) {
		var tr = this._controller;
		var o = { method: 'stats' };
		this.sendRequest( o, callback, async );
	},

	getInitialDataFor: function(dl_ids, callback) {
		var o = {
			method: "get_all_downloads"
		};

		if(dl_ids)
			o.arguments.ids = dl_ids;

        //this.sendRequest( o, function(data){ alert( data.downloads )} );
		this.sendRequest( o, function(data){ callback(data.downloads)} );
	},
	
	pauseAll: function() {

        var tribeif = this;
        
	    var o = {
	        method: "pause_all"
	    };
	    
	    // Send the request and report a message if some problems occurred
	    this.sendRequest( o, function(data){ if ( !data.success ) alert("Errors occurred while trying to pause the downloads"); } );
	    
    },

    pauseDownload: function( id ) {

        var tribeif = this;
        
	    var o = {
	        method: "pause_dl",
	        arguments: {"id" : id}
	    };
	    
	    // Send the request and report a message if some problems occurred
	    this.sendRequest( o, function(data){ if ( !data.success ) alert("Errors occurred while trying to pause the download"); } );
	    
    },


	resumeAll: function() {

        var tribeif = this;
        
	    var o = {
	        method: "resume_all"
	    };
	    
	    // Send the request and report a message if some problems occurred
	    this.sendRequest( o, function(data){ if ( !data.success ) alert("Errors occurred while trying to resume the downloads"); } );
	    
    },


    resumeDownload: function( id ) {

        var tribeif = this;
        
	    var o = {
	        method: "resume_dl",
	        arguments: {"id" : id}
	    };
	    
	    // Send the request and report a message if some problems occurred
	    this.sendRequest( o, function(data){ if ( !data.success ) alert("Errors occurred while trying to resume the download"); } );
	    
    },


    removeAll: function() {

        var tribeif = this;
        
	    var o = {
	        method: "remove_all"
	    };
	    
	    // Send the request and report a message if some problems occurred
	    this.sendRequest( o, function(data){ if ( !data.success ) alert("Errors occurred while trying to remove the downloads"); } );
	    
    },

    removeDownload: function( id ) {

        var tribeif = this;
        
	    var o = {
	        method: "remove_dl",
	        arguments: {"id" : id}
	    };
	    
	    // Send the request and report a message if some problems occurred
	    this.sendRequest( o, function(data){ if ( !data.success ) alert("Errors occurred while trying to remove the download"); } );
	    
    }


    
};

