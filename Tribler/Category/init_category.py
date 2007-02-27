# Written by Yuan Yuan
# see LICENSE.txt for license information

# give the initial category information

import ConfigParser
import os

def splitList(string):
    l = []
    for word in string.split(","):
        word = word.strip()
        l.append(word)
    return l

init_fun = {}
init_fun["minfilenumber"] = int
init_fun["maxfilenumber"] = int
init_fun["minfilesize"] = int
init_fun["maxfilesize"] = int
init_fun["suffix"] = splitList
init_fun["matchpercentage"] = float
init_fun["keywords"] = float

def getDefault():
    category = {}
    category["name"] = ""
    category["keywords"] ={}
    category["suffix"] = []
    category["minfilesize"] = 0
    category["maxfilesize"] = 10000000
    return category

def getCategoryInfo(filename):
    config = ConfigParser.ConfigParser()
    config.readfp(open(filename))

    cate_list = []
    sections = config.sections()

    for isection in sections:
        category = getDefault()
        category["name"] = isection
        for (name, value) in config.items(isection):                
            if name[0] != "*":
                category[name] = init_fun[name](value)
            else:
                name = name[1:]
                name = name.strip()
                category["keywords"][name] = init_fun["keywords"](value) 
        cate_list.append(category)   

#    print cate_list
    return cate_list

def getCategoryInfo2():
    
    overlay = []
    
    xxx = {}
    xxx["name"] = "xxx"
    xxx["keywords"] = {}
    xxx["keywords"]["fuck"] = 1         # float
    xxx["keywords"]["suck"] = 1
    xxx["keywords"]["xxx"] = 1
    xxx["keywords"]["pussy"] = 1
    xxx["keywords"]["horny"] = 1
    xxx["keywords"]["pussy"] = 1
    xxx["keywords"]["hardcore"] = 1
    xxx["keywords"]["teen"] = 0.5
    xxx["keywords"]["russian"] = 0.5
    xxx["keywords"]["american"] = 0.5
    xxx["keywords"]["girl"] = 0.5
    xxx["keywords"]["sex"] = 0.5
    xxx["suffix"] = []
    xxx["minfilesize"] = 0
    xxx["maxfilesize"] = 10000000
    xxx["minfilenumber"] = 0
    xxx["maxfilenumber"] = 10000000
    xxx["matchpercentage"] = 0.01
    
    
    Video = {}
    Video["name"] = "Video"
    Video["suffix"] = []
    Video["suffix"].append("avi")
    Video["suffix"].append("mpg")
    Video["suffix"].append("wmv")
    Video["suffix"].append("mov")
    Video["suffix"].append("mpeg")
    Video["suffix"].append("mkv")
    Video["suffix"].append("asf")
    Video["suffix"].append("vob")
    Video["suffix"].append("qicktime")
    Video["suffix"].append("rm")
    Video["suffix"].append("rmvb")
    Video["keywords"] = {}
    Video['keywords']['divx'] = 1
    Video['keywords']['xvid'] = 1
    Video['keywords']['rmvb'] = 1
    Video["minfilesize"] = 50
    Video["maxfilesize"] = 10000000
    Video["minfilenumber"] = 0
    Video["maxfilenumber"] = 10000000
    Video["matchpercentage"] = 0.5
    
    VideoClips = {}
    VideoClips["name"] = "VideoClips"
    VideoClips["suffix"] = []
    VideoClips["suffix"].append("avi")
    VideoClips["suffix"].append("mpg")
    VideoClips["suffix"].append("wmv")
    VideoClips["suffix"].append("mov")
    VideoClips["suffix"].append("mkv")
    VideoClips["suffix"].append("vob")
    VideoClips["suffix"].append("mpeg")
    VideoClips["suffix"].append("asf")
    VideoClips["suffix"].append("qicktime")
    VideoClips["suffix"].append("rm")
    VideoClips["suffix"].append("rmvb")
    VideoClips["keywords"] = {}
    VideoClips["minfilesize"] = 0
    VideoClips["maxfilesize"] = 50
    VideoClips["minfilenumber"] = 0
    VideoClips["maxfilenumber"] = 10000000
    VideoClips["matchpercentage"] = 0.5
    
    Audio = {}
    Audio["name"] = "Audio"
    Audio["suffix"] = []
    Audio["suffix"].append("mp3")
    Audio["suffix"].append("mp2")
    Audio["suffix"].append("wav")
    Audio["suffix"].append("m3u")
    Audio["suffix"].append("wma")
    Audio["suffix"].append("vorbis")
    Audio["suffix"].append("flac")
    Audio["keywords"] = {}
    Audio["minfilesize"] = 0
    Audio["maxfilesize"] = 10000000
    Audio["minfilenumber"] = 0
    Audio["maxfilenumber"] = 10000000
    Audio["matchpercentage"] = 0.8       
    
    Document = {}
    Document["name"] = "Document"
    Document["suffix"] = []
    Document["suffix"].append("doc")
    Document["suffix"].append("pdf")
    Document["suffix"].append("txt")
    Document["keywords"] = {}
    Document["minfilesize"] = 0
    Document["maxfilesize"] = 1000000
    Document["minfilenumber"] = 0
    Document["maxfilenumber"] = 1000000
    Document["matchpercentage"] = 0.8
    
    Compressed = {}
    Compressed["name"] = "Compressed"
    Compressed["suffix"] = []
    Compressed["suffix"].append("zip")
    Compressed["suffix"].append("rar")
    Compressed["suffix"].append("iso")
    Compressed["keywords"] = {}
    Compressed["keywords"][".r0"] = 1
    Compressed["keywords"][".r1"] = 1
    Compressed["keywords"][".r2"] = 1
    Compressed["keywords"][".r3"] = 1
    Compressed["keywords"][".r4"] = 1
    Compressed["keywords"][".r5"] = 1
    Compressed["keywords"][".r6"] = 1
    Compressed["keywords"][".r7"] = 1
    Compressed["keywords"][".r8"] = 1
    Compressed["keywords"][".r9"] = 1
    Compressed["minfilesize"] = 0
    Compressed["maxfilesize"] = 100000000
    Compressed["minfilenumber"] = 0
    Compressed["maxfilenumber"] = 10000000
    Compressed["matchpercentage"] = 0.8
    
    Picture = {}
    Picture["name"] = "Picture"
    Picture["suffix"] = []
    Picture["suffix"].append("jpg")
    Picture["suffix"].append("png")
    Picture["suffix"].append("bmp")
    Picture["suffix"].append("gif")
    Picture["suffix"].append("swf")
    Picture["keywords"] = {}
    Picture["minfilesize"] = 0
    Picture["maxfilesize"] = 100000000
    Picture["minfilenumber"] = 0
    Picture["maxfilenumber"] = 10000000
    Picture["matchpercentage"] = 0.8

    overlay.append(Video)
    overlay.append(VideoClips)
    overlay.append(Audio)
    overlay.append(Compressed)
    overlay.append(Document)
    overlay.append(Picture)


    overlay.append(xxx)




    print overlay
    return overlay
