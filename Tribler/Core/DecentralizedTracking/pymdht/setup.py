from distutils.core import setup

setup(
    name='Pymdht',
    version='12.2.1',
    author='Raul Jimenez and contributors',
    author_email='rauljc@gkth.se',
    packages=['pymdht', 'pymdht.core', 'pymdht.plugins', 'pymdht.ui'],
    scripts=['run_pymdht_node.py'],
    url='http://pypi.python.org/pypi/Pymdht/',
    license='LICENSE.txt',
    description='A flexible implementation of the Mainline DHT protocol.',
    long_description=open('README.rst').read(),
)
