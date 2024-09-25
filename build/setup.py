from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from packaging.version import Version
from setuptools import find_packages

from win.build import setup, setup_executables, setup_options


def read_requirements(file_name: str, directory: str = ".") -> list[str]:
    """
    Read the pip requirements from the given file name in the given directory.
    """
    file_path = os.path.join(directory, file_name)
    if not os.path.exists(file_path):
        return []
    requirements = []
    with open(file_path, encoding="utf-8") as file:
        for line in file:
            # Check for a nested requirements file
            if line.startswith("-r"):
                nested_file = line.split(" ")[1].strip()
                requirements += read_requirements(nested_file, directory)
            elif not line.startswith("#") and line.strip() != "":
                requirements.append(line.strip().split("#")[0].strip())
    return requirements


base_dir = os.path.dirname(os.path.abspath(__file__))
install_requires = read_requirements("build/requirements.txt", base_dir)
extras_require = {
    "dev": read_requirements("requirements-test.txt", base_dir),
}

# Copy src/run_tribler.py --> src/tribler/run.py to make it accessible in entry_points scripts.
# See: entry_points={"gui_scripts": ["tribler=tribler.run:main"]} in setup() below.
shutil.copy("src/run_tribler.py", "src/tribler/run.py")

# Turn the tag into a sequence of integer values and normalize into a period-separated string.
raw_version = os.getenv("GITHUB_TAG")
version_numbers = [str(value) for value in map(int, re.findall(r"\d+", raw_version))]
version = Version(".".join(version_numbers))

# cx_Freeze does not automatically make the package metadata
os.makedirs("tribler.dist-info", exist_ok=True)
with open("tribler.dist-info/METADATA", "w") as metadata_file:
    metadata_file.write(f"""Metadata-Version: 2.3
Name: Tribler
Version: {str(version)}""")

setup(
    name="tribler",
    version=str(version),
    description="Privacy enhanced BitTorrent client with P2P content discovery",
    long_description=Path("README.rst").read_text(encoding="utf-8"),
    long_description_content_type="text/x-rst",
    author="Tribler Team",
    author_email="info@tribler.org",
    url="https://github.com/Tribler/tribler",
    keywords="BitTorrent client, file sharing, peer-to-peer, P2P, TOR-like network",
    python_requires=">=3.8",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "gui_scripts": [
            "tribler=tribler.run:main",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Communications :: File Sharing",
        "Topic :: Security :: Cryptography",
        "Operating System :: OS Independent",
    ],
    options=setup_options,
    executables=setup_executables
)
