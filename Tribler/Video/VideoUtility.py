import os
import wx
import sys
import tempfile
import subprocess

from re import search
from math import sqrt
import colorsys
from Tribler.Main.vwxGUI import forceAndReturnWxThread


def get_thumbnail(videofile, thumbfile, resolution, ffmpeg, timecode):
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    ffmpeg = subprocess.Popen((ffmpeg, "-ss", str(int(timecode)), "-i", videofile, "-s", "%dx%d" % resolution, thumbfile), stderr=subprocess.PIPE, startupinfo=startupinfo)
    ffmpeg.communicate()
    ffmpeg.stderr.close()


def get_videoinfo(videofile, ffmpeg):
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    ffmpeg = subprocess.Popen((ffmpeg, "-i", videofile), stderr=subprocess.PIPE, startupinfo=startupinfo)
    out, err = ffmpeg.communicate()
    info = out or err
    ffmpeg.stderr.close()

    duration = find_duration(info)
    bitrate = find_bitrate(info)
    resolution = find_resolution(info)

    return (duration, bitrate, resolution)


def find_duration(info):
    match = search("Duration: (\\d+):(\\d+):(\\d+)\\.\\d+", info)

    if match == None:
        return 0
    h, m, s = map(int, match.groups()[:3])
    return (h * 60 + m) * 60 + s


def find_bitrate(info):
    match = search("bitrate: (\\d+) kb/s", info)

    if match == None:
        return 0
    bitrate = match.groups()
    return int(bitrate[0])


def find_resolution(info):
    match = search(", (\\d+)x(\\d+)", info)

    if match == None:
        return 0
    w, h = map(int, match.groups()[:2])
    return (w, h)


def limit_resolution(cur_res, max_res):
    if cur_res[0] <= 0 or cur_res[1] <= 0:
        return None
    aspect = cur_res[0] / float(cur_res[1])
    new_res = list(cur_res)
    if new_res[0] > max_res[0]:
        new_res[0] = max_res[0]
        new_res[1] = max_res[0] / aspect
    if new_res[1] > max_res[1]:
        new_res[1] = max_res[1]
        new_res[0] = max_res[1] * aspect
    return tuple(new_res)


def preferred_timecodes(videofile, duration, sample_res, ffmpeg, num_samples=20, k=4):
    results = []
    dest_dir = tempfile.gettempdir()
    num_samples = min(num_samples, duration)

    for timecode in range(0, duration, duration / num_samples):
        outputfile = os.path.join(dest_dir, 'tn%d.jpg' % timecode)
        get_thumbnail(videofile, outputfile, sample_res, ffmpeg, timecode)
        if os.path.exists(outputfile):
            @forceAndReturnWxThread
            def GetImageData():
                return wx.Bitmap(outputfile, wx.BITMAP_TYPE_ANY).ConvertToImage().GetData()
            results.append((colourfulness(GetImageData()), timecode))
            os.remove(outputfile)

    results.sort()
    results.reverse()
    topk = results[:k]
    return [item[1] for item in topk]


def colourfulness(image_data):
    rg_values = []
    yb_values = []

    for index in range(0, len(image_data), 3):
        r, g, b = map(ord, image_data[index:index + 3])
        rg = r - g
        yb = 0.5 * (r + g) - b
        rg_values.append(rg)
        yb_values.append(yb)

    s_rg, m_rg = meanstdv(rg_values)
    s_yb, m_yb = meanstdv(yb_values)

    s_rgyb = sqrt(s_rg ** 2 + s_yb ** 2)
    m_rgyb = sqrt(m_rg ** 2 + m_yb ** 2)

    return s_rgyb + 0.3 * m_rgyb

# Source: http://www.physics.rutgers.edu/~masud/computing/WPark_recipes_in_python.html


def meanstdv(x):
    n, mean, std = len(x), 0, 0
    for a in x:
        mean = mean + a
        mean = mean / float(n)
    for a in x:
        std = std + (a - mean) ** 2
    std = sqrt(std / float(n - 1))
    return mean, std

# def considered_xxx(image):
#    return skinratio(image) > 0.50
#
# def skinratio(image):
#    image_data = image.GetData()
#    skin_pixels = total_pixels = 0
#
#    for index in range(0, len(image_data), 3):
#        r, g, b = map(ord, image_data[index:index+3])
#        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
#        if h >= 0 and h <= 25 and s >= 0.15 and s <= 0.90 and v >= 0.20 and v <= 0.95:
#            skin_pixels += 1
#        total_pixels += 1
#
#    return skin_pixels/float(total_pixels)
