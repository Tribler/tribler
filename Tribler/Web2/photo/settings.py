
ENCODING = "utf-8"

RE_LICENSE=r'http://creativecommons.org/licenses/by-nc-nd/2.0/'

URL_SEARCH="http://www.flickr.com/search/?q=%s&l=3&m=tags&page=%d"
URL_ITEM="http://www.flickr.com/photos/%s"

RE_SEARCHITEM = r'<td class="DetailPic">.*?href="/photos/(.*?)".*?<img src="(.*?)".*?<td class="PicDesc">'
RE_ITEMTAGS = r"tagsA\.push\('(.*?)'\)"
RE_ITEMTITLE = r'<h1 id="[^"]*">(.*?)</h1>'
RE_ITEMBY = r'by <a href=".*?" title=".*?"><b>(.*?)</b></a>'
URL_DLPHOTO = "http://www.flickr.com/photo_zoom.gne?id=%s&size=o"
RE_ORGSIZE = r'<a href="(.*?)">Download the .*? size</a>' 

RE_NUMID = "[^/]*/(.*)"

