"""
File containing function used in credit mining module.
"""
import os
from binascii import hexlify, unhexlify

from Tribler.Core.CreditMining.defs import SIMILARITY_TRESHOLD


def validate_source_string(source):
    """
    Function to check whether a source string is a valid source or not
    """
    return unhexlify(source) if len(source) == 40 and not source.startswith("http") else source


def levenshtein_dist(t1_fname, t2_fname):
    """
    Calculates the Levenshtein distance between a and b.

    Levenshtein distance (LD) is a measure of the similarity between two strings.
    (from http://people.cs.pitt.edu/~kirk/cs1501/Pruhs/Fall2006/Assignments/editdistance/Levenshtein%20Distance.htm)
    """
    len_t1_fname, len_t2_fname = len(t1_fname), len(t2_fname)
    if len_t1_fname > len_t2_fname:
        # Make sure len_t1_fname <= len_t2_fname, to use O(min(len_t1_fname,len_t2_fname)) space
        t1_fname, t2_fname = t2_fname, t1_fname
        len_t1_fname, len_t2_fname = len_t2_fname, len_t1_fname

    current = range(len_t1_fname + 1)
    for i in xrange(1, len_t2_fname + 1):
        previous, current = current, [i] + [0] * len_t1_fname
        for j in xrange(1, len_t1_fname + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if t1_fname[j - 1] != t2_fname[i - 1]:
                change += 1
            current[j] = min(add, delete, change)

    return current[len_t1_fname]


def source_to_string(source_obj):
    return hexlify(source_obj) if len(source_obj) == 20 and not (source_obj.startswith('http://')
                                                                 or source_obj.startswith('https://')) else source_obj


def string_to_source(source_str):
    # don't need to handle null byte because lazy evaluation
    return source_str.decode('hex') \
        if len(source_str) == 40 and not (os.path.isdir(source_str) or source_str.startswith('http://')) else source_str


def compare_torrents(torrent_1, torrent_2):
    """
    comparing swarms. We don't want to download the same swarm with different infohash
    :return: whether those t1 and t2 similar enough
    """
    files1 = [files for files in torrent_1['metainfo'].get_files_with_length() if files[1] > 1024 * 1024]
    files2 = [files for files in torrent_2['metainfo'].get_files_with_length() if files[1] > 1024 * 1024]

    if len(files1) == len(files2):
        for ft1 in files1:
            for ft2 in files2:
                if ft1[1] != ft2[1] or levenshtein_dist(ft1[0], ft2[0]) > SIMILARITY_TRESHOLD:
                    return False
        return True
    return False


def ent2chr(input_str):
    """
    Function to unescape literal string in XML to symbols
    source : http://www.gossamer-threads.com/lists/python/python/177423
    """
    code = input_str.group(1)
    code_int = int(code) if code.isdigit() else int(code[1:], 16)
    return chr(code_int) if code_int < 256 else '?'
