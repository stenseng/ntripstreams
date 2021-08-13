Installation
============

End users can install ntripstreams using pip

.. code-block::
    pip install ntripstreams

To run ntripstreams in a conda development environment use the dev_environment.yml.

.. code-block::
    (base)$ mkdir Ntripstreams
    (base)$ cd Ntripstreams
    (base)$ git clone https://github.com/stenseng/ntripstreams.git .
    (base)$ conda env create --file dev_environment.yml
    (base)$ conda activate ntrip
    (ntrip)$ pip install -e .
