/*
 *	Written by Riccardo Petrocco
 *	see LICENSE.txt for license information
 * 
 */

function Tribe(){
	this.initialize();
}

Tribe.prototype =
{
	/*--------------------------------------------
	 *
	 *  C O N S T R U C T O R
	 *
	 *--------------------------------------------*/

	initialize: function()
	{
		// Initialize the helper classes
		this.tribeif = new TribeInterface(this);
		

		// Initialize the implementation fields
		this._downloads               = { };
		this._dllist                  = [ ];
		this._activeDLs               = 0;
		this._refreshSec              = 3;
		this._BPClosed                = false;
	    this._justPaused              = false;


        // Set up user events
		var controller = this;
		var tribe = this;

		$('#pause_all').bind('click', function(e){ controller.pauseAll(e); });
		$('#resume_all').bind('click', function(e){ controller.resumeAll(e); });
		$('#remove_all').bind('click', function(e){ controller.removeAll(e); });
		
		$('#pause_all').mouseover( function(){ $(".head_button:first").css("background-image", "url(webUI/images/users_arrow_red.png)"); } );
		$('#pause_all').mouseout( function(){ $(".head_button:first").css("background-image", "url(webUI/images/users_arrow_red_light.png)"); } );
		
		$('#resume_all').mouseover( function(){ $(".head_button:odd").css("background-image", "url(webUI/images/users_arrow_green.png)"); } );
		$('#resume_all').mouseout( function(){ $(".head_button:odd").css("background-image", "url(webUI/images/users_arrow.png)"); } );


//		$('#pause_all').mouseover( function(){ $(".head_button:first").backgroundImage = "url(webUI/images/pause_big.png)"; } );
//        $('#pause_all').mouseover( $(this).children.attr("id", "ooo")) );
		this._downloads_list = $('#downloads_list')[0];
		

		// TODO
		this.initializeAllTorrents();

        var timeout = this._refreshSec * 1000
        setTimeout("tribe.reload(true)", timeout);
        
	},


	/*--------------------------------------------
	 *
	 *  U T I L I T I E S
	 *
	 *--------------------------------------------*/
    
	initializeAllTorrents: function(){
	
	    if (this._downloads.length > 0) {
	        this._downloads = {};
	    }
		var tr = this;
		this.tribeif.getInitialDataFor( null ,function(downloads) { tr.addDownloads(downloads); } );
	},

	addDownloads: function( new_downloads )
	{
	
	    // new_downloads is a list of downloads
		var fragment = document.createDocumentFragment( );

		for( var i=0, row; row=new_downloads[i]; ++i ) {
			var newDL = new Download( fragment, this, row );
			this._downloads[newDL.id()] = newDL;
		}
		
		this.updateDLList();

        // torrent container in HTML
        $('#downloads_list').append( fragment );
        

        // TODO update!
		this.refreshStats( );
	},
	
	pauseAll: function( event )
	{
	    var controller = this;
	    controller.tribeif.pauseAll();
	    
	    $('li.dl').fadeTo("slow", 0.3);
	    this._justPaused = true;
	    //this.setHeadButtons("resume");
	    //$('#pause_all_link').parent().attr("id", "resume_all");
	    
	},
	
	pauseDownload: function( id )
	{
	    var controller = this;
	    controller.tribeif.pauseDownload( id );

        // JQuery does not accept special char like the '%'
        // we have as id :-(.. so replace it
        var encID = this.replaceSpecialChar(id, '%', "\\%");

        $('#' + encID).fadeTo("slow", 0.3);
        this._justPaused = true;
//        $('#' + encID).fadeIn("slow");
	    
	    //controller.reload(false);
	},
	
	resumeAll: function( event )
	{
	    var controller = this;
	    controller.tribeif.resumeAll();
	    $('li.dl').fadeTo("slow", 1);
	},
	
	resumeDownload: function( id )
	{
	    var controller = this;
	    controller.tribeif.resumeDownload( id );

        var encID = this.replaceSpecialChar(id, '%', "\\%");

        $('#' + encID).fadeTo("slow", 1);
	    
	},


	removeAll: function( event )
	{
	    var controller = this;
	    controller.tribeif.removeAll();
	    
	    $('li.dl').hide("slow");
	    
	    this._downloads = {};
        this.updateDLList();
	    
	},
	
	
	removeDownload: function( id )
	{
	    var controller = this;
	    controller.tribeif.removeDownload( id );

        // JQuery does not accept special char like the '%'
        // we have as id :-(.. so replace it
        var encID = this.replaceSpecialChar(id, '%', "\\%");
        
        // remove from list, causing problems when reloading
        //alert(this._dllist);
//        this._dllist.splice(this._dllist.indexOf(id), 1);
//        alert(this._dllist);        
        delete this._downloads[id];
        this.updateDLList();
        
        $('#' + encID).hide("slow");

	},
	
	
	updateDLList: function()
	{
	    var dllist = [];
	    var dls = this._downloads;
	  
	    for (var key in dls){
	        dllist.push( key );
	    }
	    
	    this._dllist = dllist;
	},
	
	reload: function( schedule )
	{
//        alert("reload");
		var tr = this;
		this.tribeif.getInitialDataFor( null ,function(downloads) 
		    {
                if (downloads) {
		            // don't use effects adding torrents if we are just 
		            // updating the current list
		            // TODO now checking only the changes in amount of downloads.
		            // There might be problems when removing and adding a download 
		            // at the same time => ignore since it's not possible trough the interface!
		            if ( downloads.length == tr._dllist.length ) {
		                tr.updateDownloads(downloads);
		            }
		            
		            else {
		            
		                // if we started a new video
		                if ( downloads.length > tr._dllist.length ) {
		                    // add the new downloads
		                    tr.fadeInDL(downloads);
		                }
		                
		                else if ( downloads.length < tr._dllist.length ) {

		                    // it might be that the downloads have been removed
		                    // by the engine since it has not been completly downloaded
                		    var n = 0;
                		    while ( n<tr._dllist.length) {                        
                		    
                                var missing = true;                		    
                    		    for( var i=0, dl; dl=downloads[i]; ++i ) {   
                    		        if (tr._dllist[n] == dl.id) { 
                                        missing = false;
                                    }
                                }
                                
                                if (missing) {
                                    var encID = tr.replaceSpecialChar(tr._dllist[n], '%', "\\%");
                                    delete tr._downloads[ tr._dllist[n] ];
                                    tr.updateDLList();
                                    $('#' + encID).hide("slow");                                
                                }
                                
                                n++;
                            }
                            tr.refreshStats();

		                }
                    		    		                
		                else {
		                    alert ("TODO, different size");
	                    }
	                    
		            }
                }		        		        
	        } );
	        
	    if ( schedule && !this._BPClosed) {
	        var timeout = this._refreshSec * 1000
	        setTimeout("tribe.reload(true)", timeout);
	    }

	},
	
	updateDownloads: function( dls )
	{

        this._activeDLs = 0;
        // Check if we are considering the same torrents.
		for( var i=0, dl; dl=dls[i]; ++i ) {

            var n=0;
            var confirm = false;
            while ( n<this._dllist.length ) {
                
                if (this._dllist[n] == dl.id) {
//alert(this._downloads[ this._dllist[n] ]._status );
                    // we update the statistics only if all the 
                    // downloads are currently active!
                    if (dl.status != "DLSTATUS_STOPPED") {
                    //if (this._downloads[ this._dllist[n] ]._status != "DLSTATUS_STOPPED") {
                        this._activeDLs++;
                    }
                    
                    
                    confirm = true;
                }
                
                n++;
            }
            
            // it might be that we changed page while a video was
            // playing. => the video seems replaced
            if (confirm == false) {
                //TODO check, this is a hack to have an item reload
                this._justPaused = true;
                //alert("TODO, different hash"); 
                //break;
            }

		}
//        alert(activeDLs);
//        alert(this._dllist.length);
        // Update the active downloads
        
        // Replace all the list if all the downloads are being 
        // updated
        if (this._activeDLs || this._justPaused) {		
            this._justPaused = false;
		    // Remove the list of downloads and recreate it
            $('#downloads_list').children(".dl").remove();

            this.addDownloads( dls );
        }

        this.setHeadButtons();
        //else { alert(activeDLs); }

	},
	
	
	// Now it just appends the new dowloads at the end of the list
	// TODO put them in order immediatly
	fadeInDL: function( downloads ) {
	
	    this._activeDLs = 0;
	    var fragment = document.createDocumentFragment( );
        var newDLs = [];
        
		for( var i=0, row; row=downloads[i]; ++i ) {
		    
		    var n=0;
            var missing = true;


            while ( n<this._dllist.length && missing) {

                if (this._dllist[n] == row.id) {
                    missing = false;
                }

                ++n;
            }
            
            if (missing) {
                newDLs.push(row);
            }
            
            if (row._status != "DLSTATUS_STOPPED") {
                this._activeDLs++;
            }
    		
		}
		
	    if (newDLs.length > 0) {

     		for( var i=0, row; row=newDLs[i]; ++i ) {
			    // create the new download elements
			    var newDL = new Download( fragment, this, row );
			    this._downloads[newDL.id()] = newDL;
		    }
                   		
		}
		
		this.updateDLList();

        this.setHeadButtons();
        // torrent container in HTML
        $('#downloads_list').append( fragment );
	},
	
	refreshStats: function()
	{
	    var num_dl = this._dllist.length;

        $('#num_dls')[0].innerHTML =  num_dl;
        
        var totUP = 0;
        var totDOWN = 0;
        
        
        for (var id in this._downloads)
        {
            totUP += parseFloat( this._downloads[id]._UPspeed );
            totDOWN += parseFloat( this._downloads[id]._DOWNspeed );
          
        }
        
        $('#total_upload')[0].innerHTML =  totUP.toFixed(2) + " KB/s";
        $('#total_download')[0].innerHTML =  totDOWN.toFixed(2) + " KB/s";

	},
	
	replaceSpecialChar: function(stringIn, oldChar, newString)
	{
	    var tmp = stringIn.split( oldChar );

	    var res = "";
	    
	    for (i in tmp)
	    {
	        if (tmp[i] != '')
	        {
                res += newString + tmp[i];   
	        }
	    }
	    
	    return res;

	},
	
	setHeadButtons: function ()
	{
	    
	    var button = $('#pause_resume_all').children();
	    
	    // check which should be the status
	    if (this._activeDLs || !this._dllist.length ) {
	        //
            $('#resume_all').hide();
            $('#pause_all').show();
	//        alert(this._activeDLs);
    //	    $('#pause_resume_all').parent().attr("id", "pause_all");
    //        button.css("background-image", "url(webUI/images/pause_big.png)");
    //        alert(button.text());
//	        $('#pause_all').mouseover( function(){ $(".head_button:first").css("background-image", "url(webUI/images/pause_big_blue.png)"); } );
	    }
	    
	    // show the resume button
	    
	    else {
            $('#pause_all').hide();
            $('#resume_all').show();
//    	    $('#pause_resume_all').parent().attr("id", "resume_all");
//            button.css("background-image", "url(webUI/images/resume_big.png)");
	    }
	}
	
};
