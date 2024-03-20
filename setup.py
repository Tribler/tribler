import os
import re
import shutil
from pathlib import Path

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


def read_requirements(file_name, directory='.'):
    file_path = os.path.join(directory, file_name)
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


setup(
    name="Tribler",
    version=version,
    description="Privacy enhanced BitTorrent client with P2P content discovery",
    long_description=Path('README.rst').read_text(encoding="utf-8"),
    long_description_content_type="text/x-rst",
    author="Tribler Team",
    author_email="info@tribler.org",
    url="https://www.tribler.org",
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
        "License :: OSI Approved :: GPL-3.0 license",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Internet :: File Sharing",
        "Topic :: Security :: Cryptography",
        "Operating System :: OS Independent",
    ],
)
