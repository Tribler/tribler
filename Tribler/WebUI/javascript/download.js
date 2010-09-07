/*
 *	Written by Riccardo Petrocco
 *	see LICENSE.txt for license information
 * 
 */

function Download( fragment, controller, data) {
	this.initialize( fragment, controller, data);
}


Download.prototype =
{

	initialize: function( fragment, controller, data) 
	{
		this._id        = data.id;
        this._name      = data.name;
        this._status    = data.status;
        this._progress  = data.progress;
        this._UPspeed   = data.upload.toFixed(2);
        this._DOWNspeed = data.download.toFixed(2);


		// Create a new <li> element
		var main = document.createElement( 'li' );
		main.className = 'dl';
		main.id = this._id;
		main._dl = this;
		var element = $(main);
		element._dl = this;
		this._element = element;
		this._controller = controller;
		
		// TODO check, we are updating the dllist multiple times
		controller._dllist.push( element );
		
		// Create the 'name' <div>
		var e = document.createElement( 'div' );
		e.className = 'dl_name';
		main.appendChild( e );
		element._name_dl = e;
		
		// Create the 'speeds' <div>
		var e = document.createElement( 'div' );
		e.className = 'dl_speeds';
		main.appendChild( e );
		element._speeds_dl = e;
		
		// Create the 'progress bar container' <div>
		e = document.createElement( 'div' );
		e.className = 'dl_progress_bar_container';

        // Crate the 'progress bar' <div>
		i = document.createElement( 'div' );
		i.className = 'dl_progress_bar';
		progressID = 'progress_' + this._id;
		i.id = progressID;
		element._progress_dl = i;
		
		e.appendChild(i);
		main.appendChild( e );

        // Create image container
        var container = document.createElement( 'div' );
        container.className = 'control_container';

        // Remove button
        var remove = document.createElement( 'div' );
		remove.className = 'remove_dl';
		e = document.createElement( 'a' );
		e.appendChild( remove );
		
		container.appendChild( e );
		element._remove_button = remove;
		$(e).bind('click', function(e) { element._dl.clickRemoveButton(e); });
		$(remove).bind('mouseover', function() { $(remove).css("background-image", "url(webUI/images/remove_red.png)"); });
		$(remove).bind('mouseout', function() { $(remove).css("background-image", "url(webUI/images/remove.png)"); });				

		// Pause button
		var pause = document.createElement( 'div' );
		pause.className = 'pause_dl';
		e = document.createElement( 'a' );
		e.appendChild( pause );
		container.appendChild( e );
		element._pause_button = pause;
		$(e).bind('click', function(e) { element._dl.clickPauseButton(e); });
		$(pause).bind('mouseover', function() { $(pause).css("background-image", "url(webUI/images/pause_red.png)"); });
		$(pause).bind('mouseout', function() { $(pause).css("background-image", "url(webUI/images/pause.png)"); });


//		$(e).bind('mouseover', function() { $("div.pause_dl").css("background-image", "url(webUI/images///pause_blue.png)"); });
//		$(e).bind('mouseout', function() { $("div.pause_dl").css("background-image", "url(webUI/images/pause.png)"); });				

		
		// Resume button
		var resume = document.createElement( 'div' );
		resume.className = 'resume_dl';
		e = document.createElement( 'a' );
		e.appendChild( resume );
		
		container.appendChild( e );
		element._resume_button = resume;
		$(e).bind('click', function(e) { element._dl.clickResumeButton(e); });
		$(resume).bind('mouseover', function() { $(resume).css("background-image", "url(webUI/images/resume_green.png)"); });
		$(resume).bind('mouseout', function() { $(resume).css("background-image", "url(webUI/images/resume.png)"); });				
		
		main.appendChild( container );

		// Update progress bar
		percentual = Math.floor(100 * this._progress);
        i.style.width = percentual + '%';

		// Update all the labels etc
		this._element._name_dl.innerHTML = this._name + '  ' + percentual + '%';
		this._element._speeds_dl.innerHTML = "Download speed: " + this._DOWNspeed + " KB/s  |  Upload speed: " + this._UPspeed + " KB/s";
		


		if (this._status == "DLSTATUS_STOPPED") 
		{
		    i.style.backgroundImage = "url(webUI/images/progress_red.png)";
		    pause.style.display = "none";
		    main.style.opacity = 0.3;
		}
		
		if (this._status == "DLSTATUS_DOWNLOADING") 
		{
		    i.style.backgroundImage = "url(webUI/images/progress_blue.png)";	    	
		    resume.style.display = "none";
		}
		
		if (this._status == "DLSTATUS_SEEDING") 
		{
		    i.style.backgroundImage = "url(webUI/images/progress_green.png)";	    			
		    resume.style.display = "none";
		}
		// insert the element
		fragment.appendChild(main);
	},
	
	
	clickRemoveButton: function( event )
	{
	    this._controller.removeDownload( this._id );
	},
	
	clickPauseButton: function(event)
	{
	    this._controller.pauseDownload( this._id );
	},
	
	clickResumeButton: function(event)
	{
	    this._controller.resumeDownload( this._id );
	},	
	
    id: function() { return this._id; },
}


