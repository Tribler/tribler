import logging
import time
import xml.etree.ElementTree as xml
from argparse import ArgumentParser
from pathlib import Path

import defusedxml.ElementTree as defxml

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def parse_arguments():
    parser = ArgumentParser(description='Update Tribler metainfo.xml')
    parser.add_argument('-r', '--repo', type=str, help='path to a repository folder', default='.')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()

    version = Path('.TriblerVersion').read_text().lstrip('v').rstrip('\n')

    release_info = {
        'version': version,
        'date': time.strftime("%Y-%m-%d", time.localtime())
    }

    logger.info(f'Release info: {release_info}')
    metainfo_xml = Path(arguments.repo) / 'build/debian/tribler/usr/share/metainfo/org.tribler.Tribler.metainfo.xml'

    xml_dom = defxml.parse(metainfo_xml)
    releases = xml_dom.getroot().find('releases')
    release = xml.SubElement(releases, 'release', release_info)

    xml_dom.write(metainfo_xml, encoding='utf-8', xml_declaration=True)
    logger.info(f'Content of metainfo.xml: {metainfo_xml.read_text()}')
