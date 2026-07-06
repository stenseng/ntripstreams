ntripstreams
============

**ntripstreams** is a Python library and command line tool for transferring
GNSS and related data between GNSS instruments, NTRIP casters and users using
the NTRIP protocol. It provides simple, logical, ``asyncio``-based methods to
communicate with GNSS receivers and casters, and to frame and decode RTCM 3
messages.

.. code-block:: console

    $ pip install ntripstreams

Quick start
-----------

List the source table of a caster:

.. code-block:: console

    $ ntripstreams http://caster.example.net:2101

Stream and decode RTCM 3 from a mountpoint:

.. code-block:: console

    $ ntripstreams http://caster.example.net:2101 -m MOUNT1 -u USER -p PASSWORD -v

Credentials and connection details can also be supplied through the
environment (``NTRIP_URL``, ``NTRIP_MOUNTPOINT``, ``NTRIP_USER``,
``NTRIP_PASSWORD``, ``NTRIP_LOGFILE``); a command line value always overrules
the matching environment variable.

.. toctree::
    :maxdepth: 2
    :caption: Contents:

    install
    ntripstreams

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
