import os
import re
import shutil

from setuptools import setup, find_packages

# Copy src/run_tribler.py --> src/tribler/run.py to make it accessible in entry_points scripts.
shutil.copy("src/run_tribler.py", "src/tribler/run.py")


def read_version_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        file_content = file.read()
    # Use regular expression to find the version pattern
    version_match = re.search(r"^version_id = ['\"]([^'\"]*)['\"]", file_content, re.M)
    if version_match:
        version_str = version_match.group(1)
        return version_str.split("-")[0]
    raise RuntimeError("Unable to find version string.")


version_file = os.path.join('src', 'tribler', 'core', 'version.py')
version = read_version_from_file(version_file)


setup(
    name="Tribler",
    version=version,
    description="Privacy enhanced BitTorrent client with P2P content discovery",
    long_description=open('README.rst').read(),
    long_description_content_type="text/x-rst",
    author="Tribler Team",
    author_email="tribler@tribler.org",
    url="https://www.tribler.org",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "aiohttp==3.9.0",
        "aiohttp-apispec==2.2.3",
        "anyio==3.7.1",
        "chardet==5.1.0",
        "configobj==5.0.8",
        "cryptography==42.0.5",
        "Faker==18.11.2",
        "libnacl==1.8.0",
        "lz4==4.3.2",
        "marshmallow==3.19.0",
        "networkx==3.1",
        "pony==0.7.17",
        "psutil==5.9.5",
        "pydantic==1.10.11",
        "PyOpenSSL==24.0.0",
        "pyyaml==6.0",
        "sentry-sdk==1.31.0",
        "yappi==1.4.0",
        "yarl==1.9.2",
        "bitarray==2.7.6",
        "pyipv8==2.13.0",
        "libtorrent==1.2.19",
        "file-read-backwards==3.0.0",
        "Brotli==1.0.9",
        "human-readable==1.3.2",
        "colorlog==6.7.0",
        "filelock==3.13.0",
        "ipv8-rust-tunnels==0.1.17",
        "Pillow==10.2.0",
        "PyQt5==5.15.1",
        "PyQt5-sip==12.8.1",
        "pyqtgraph==0.12.3",
        "PyQtWebEngine==5.15.2",
        "setuptools==65.5.1; sys_platform == 'darwin'",
        "text-unidecode==1.3; sys_platform == 'darwin'",
        "defusedxml==0.7.1; sys_platform == 'linux2' or sys_platform == 'linux'",
        "markupsafe==2.0.1; sys_platform == 'linux2' or sys_platform == 'linux'",
        "PyGObject==3.44.1; sys_platform == 'linux2' or sys_platform == 'linux'",
        "requests==2.31.0",
    ],
    extras_require={
        "dev": [
            "pytest==7.4.3",
            "pytest-aiohttp==1.0.5",
            "pytest-asyncio==0.21.1",
            "pytest-randomly==3.15.0",
            "pytest-timeout==2.2.0",
            "pylint-pytest==1.1.7",
            "coverage==7.3.2",
            "looptime==0.2;sys_platform!='win32'",
            "pytest-qt==4.2.0",
        ],
    },
    entry_points={
        "gui_scripts": [
            "tribler=tribler.run:main",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GPL-3.0 license",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Internet :: File Sharing",
        "Topic :: Security :: Cryptography",
        "Operating System :: OS Independent",
    ],
)
