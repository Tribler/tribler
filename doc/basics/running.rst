Running Tribler from Source
===========================

In order to run Tribler from its source you will need to perform some setup.
We assume you have ``git`` and ``python`` installed.
If you want to run a GUI for Tribler, you will need ``npm`` installed too.


Steps
-----

1. Clone the Tribler repo:

.. code-block::

    git clone --recursive https://github.com/tribler/tribler

.. warning::
 Tribler uses submodules.
 If you (1) download the ZIP or (2) forget to recursively clone, your ``pyipv8`` folder will be empty.
 Repair the former by `downloading the IPv8 zip <https://github.com/Tribler/py-ipv8>`_ and extracting it in the ``pyipv8`` folder and repair the latter by running ``git submodule update --init``.
    
2. Install the python dependencies:

.. code-block::

    python -m pip install --upgrade -r tribler/requirements.txt

3. Build the GUI:

.. code-block::

    cd src/tribler/ui/
    npm install
    npm run build

4. Add the IPv8 submodule to your ``PYTHONPATH``. For example, (Windows) ``set PYTHONPATH=%PYTHONPATH%;pyipv8``, (Linux) ``export PYTHONPATH="${PYTHONPATH}:pyipv8"`` or (PyCharm) right click the ``pyipv8`` folder and ``Mark Directory as/Sources Root``.

5. Run Tribler:

.. code-block::

    cd src
    python run_tribler.py

Sometimes, you may run into platform-specific issues.
If this is your case, continue reading for your appropriate platform.
