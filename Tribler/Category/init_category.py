# Written by Yuan Yuan
# see LICENSE.txt for license information

# give the initial category information

import ConfigParser

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
init_fun["strength"] = float
init_fun["displayname"] = str
init_fun["rank"] = int

def getDefault():
    category = {}
    category["name"] = ""
    category["keywords"] ={}
    category["suffix"] = []
    category["minfilesize"] = 0
    category["maxfilesize"] = -1
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
