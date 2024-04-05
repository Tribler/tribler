import os
import re
import shutil
from pathlib import Path

from setuptools import find_packages

from build.win.build import setup, setup_options, setup_executables


def read_version_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        file_content = file.read()
    # Use regular expression to find the version pattern
    version_match = re.search(r"^version_id = ['\"]([^'\"]*)['\"]", file_content, re.M)
    if version_match:
        version_str = version_match.group(1)
        return version_str.split("-")[0]
    raise RuntimeError("Unable to find version string.")


def read_requirements(file_name, directory='.'):
    file_path = os.path.join(directory, file_name)
    if not os.path.exists(file_path):
        return []
    requirements = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # Check for a nested requirements file
            if line.startswith('-r'):
                nested_file = line.split(' ')[1].strip()
                requirements += read_requirements(nested_file, directory)
            elif not line.startswith('#') and line.strip() != '':
                requirements.append(line.strip().split('#')[0].strip())
    return requirements


base_dir = os.path.dirname(os.path.abspath(__file__))
install_requires = read_requirements('requirements-build.txt', base_dir)
extras_require = {
    'dev': read_requirements('requirements-test.txt', base_dir),
}

# Copy src/run_tribler.py --> src/tribler/run.py to make it accessible in entry_points scripts.
# See: entry_points={"gui_scripts": ["tribler=tribler.run:main"]} in setup() below.
shutil.copy("src/run_tribler.py", "src/tribler/run.py")

# Read the version from the version file: src/tribler/core/version.py
# Note that, for version.py to include the correct version, it should be generated first using git commands.
# For example:
#    git describe --tags | python -c "import sys; print(next(sys.stdin).lstrip('v'))" > .TriblerVersion
#    git rev-parse HEAD > .TriblerCommit
# Then, the version.py file can be generated using the following command:
#    python build/update_version.py
version_file = os.path.join('src', 'tribler', 'core', 'version.py')
version = read_version_from_file(version_file)

setup(
    name="tribler",
    version=version,
    description="Privacy enhanced BitTorrent client with P2P content discovery",
    long_description=Path('README.rst').read_text(encoding="utf-8"),
    long_description_content_type="text/x-rst",
    author="Tribler Team",
    author_email="info@tribler.org",
    url="https://github.com/Tribler/tribler",
    keywords='BitTorrent client, file sharing, peer-to-peer, P2P, TOR-like network',
    python_requires='>=3.8',
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Communications :: File Sharing",
        "Topic :: Security :: Cryptography",
        "Operating System :: OS Independent",
    ],
    options=setup_options,
    executables=setup_executables
)
