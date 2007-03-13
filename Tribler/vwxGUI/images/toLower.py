#!/usr/local/bin/python


import re, os



for fname in os.listdir(os.getcwd()):

	if fname[-3:] == 'png' or fname[-3:] == 'jpg':
		print fname

	        
        	c = os.path.splitext(fname)
	
		new = c[0].lower()+c[1]
		print new
		os.rename(fname, new)