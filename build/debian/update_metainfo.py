from os import getenv
from time import localtime, strftime
from xml.etree.ElementTree import SubElement, parse

if __name__ == "__main__":
    metainfo_xml = "build/debian/tribler/usr/share/metainfo/org.tribler.Tribler.metainfo.xml"
    tree = parse(metainfo_xml)
    root = tree.getroot()
    releases_tag = root.find("releases")
    SubElement(releases_tag, "release", {"version": getenv("GITHUB_TAG"), "date": strftime("%Y-%m-%d", localtime())})
    tree.write(metainfo_xml, encoding="utf-8", xml_declaration=True)
