
import util.db

import video.youtube
import video.liveleak

video

typesearches = {
        "video" : [ video.liveleak.LiveLeakSearch, video.youtube.YoutubeSearch]
        }


def web2query(query, type):

    searches = []
    for search in typesearches[type]:
        searches.append(search(query))

    return util.db.CompoundDBSearch(searches)


    
