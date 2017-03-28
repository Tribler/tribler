"""
Video utilities.

Author(s): Egbert Bouman
"""
import os
import sys
import tempfile
import subprocess

from re import search
from math import sqrt

from PIL import Image

from Tribler.Core.osutils import is_android


def get_thumbnail(videofile, thumbfile, resolution, ffmpeg, timecode):
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    ffmpeg = subprocess.Popen((ffmpeg.encode('utf-8'),
                               "-ss", str(int(timecode)),
                               "-i", videofile.encode('utf-8'),
                               "-s", "%dx%d" % resolution,
                               thumbfile.encode('utf-8')),
                              stderr=subprocess.PIPE, startupinfo=startupinfo)
    ffmpeg.communicate()
    ffmpeg.stderr.close()


def get_videoinfo(videofile, ffmpeg):
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    ffmpeg = subprocess.Popen((ffmpeg.encode('utf-8'), "-i", videofile.encode('utf-8')),
                              stderr=subprocess.PIPE, startupinfo=startupinfo)
    out, err = ffmpeg.communicate()
    info = out or err
    ffmpeg.stderr.close()

    duration = find_duration(info)
    bitrate = find_bitrate(info)
    resolution = find_resolution(info)

    return duration, bitrate, resolution


def find_duration(info):
    match = search("Duration: (\\d+):(\\d+):(\\d+)\\.\\d+", info)

    if match is None:
        return 0
    h, m, s = map(int, match.groups()[:3])
    return (h * 60 + m) * 60 + s


def find_bitrate(info):
    match = search("bitrate: (\\d+) kb/s", info)

    if match is None:
        return 0
    bitrate = match.groups()
    return int(bitrate[0])


def find_resolution(info):
    match = search(", (\\d+)x(\\d+)", info)

    if match is None:
        return 0
    w, h = map(int, match.groups()[:2])
    return w, h


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
            # Android doesn't have wx, use PIL instead
            if is_android():
                def get_image_data():
                    im = Image.open(outputfile)
                    return list(im.getdata())
            else:
                import wx
                from Tribler.Main.vwxGUI import forceAndReturnWxThread

                @forceAndReturnWxThread
                def get_image_data():
                    pxls = []
                    wxstr = wx.Bitmap(outputfile, wx.BITMAP_TYPE_ANY).ConvertToImage().GetData()
                    for index in range(0, len(wxstr), 3):
                        pxls.append(tuple(map(ord, wxstr[index:index + 3])))
                    return pxls

            this_colour = colourfulness(get_image_data())
            if this_colour is not None:
                results.append((this_colour, timecode))
                if os.path.exists(outputfile):
                    os.remove(outputfile)

    results.sort()
    results.reverse()
    topk = results[:k]
    return [item[1] for item in topk]


def colourfulness(image_data):
    if image_data:
        rg_values = []
        yb_values = []

        for pxl in image_data:
            r, g, b = pxl
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
        mean += a
        mean /= float(n)
    for a in x:
        std += (a - mean) ** 2
    std = sqrt(std / float(n - 1))
    return mean, std


def considered_xxx(image_file, filter_ratio=0.30):
    return skinratio(image_file) > filter_ratio


def skinratio(image_fie):
    try:
        image = Image.open(image_fie).convert('RGB')

        image = image.resize((int(image.size[0] * 0.20), int(image.size[1] * 0.20)))
        image_data = list(image.getdata())
        skin_pixels = total_pixels = 0

        for index in range(0, len(image_data)):
            r, g, b = image_data[index]
            if r > 60 and g < (r * 0.85) and b < (r * 0.7) and g > (r * 0.4) and b > (r * 0.2):
                skin_pixels += 1
            total_pixels += 1
        if total_pixels == 0:
            return 0
        return skin_pixels / float(total_pixels)
    except:
        return 0
