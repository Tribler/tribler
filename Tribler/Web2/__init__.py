# Written by Fabian van der Werf, Jelle Roozenburg
# see LICENSE.txt for license information

import util.db

from video.genericsearch import GenericSearch
from util.update import Web2Config


def web2query(query, type, gui_utility):
    web2config = Web2Config.getInstance(gui_utility.utility)
    searches = []
    for searchname in web2config.getWeb2Sites(type):
        
        if searchname == "youtube":
            continue
        
        searches.append(GenericSearch(searchname, query, web2config))

    return util.db.CompoundDBSearch(searches,gui_utility.standardOverview)


    
