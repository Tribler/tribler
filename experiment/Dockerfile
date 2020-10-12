# Dockerfile to build Tribler core image used for experiments.

# The base image: 'triblercore/libtorrent:1.2.10-x' is a separately compiled version of libtorrent with BEP33 support.
# Check: https://jenkins-ci.tribler.org/job/docker/job/build-libtorrent/
# Note: permission is required to access Jenkins job configuration.

# Usage: run docker build from the project root (tribler) directory
# Eg. docker build -t triblercore/experiment:torrent_health -f experiment/Dockerfile .

FROM triblercore/libtorrent:1.2.10-x

# Update the base system and install required non-pip dependencies
RUN apt update && apt upgrade -y
RUN apt install -y libsodium23 python3-pip git

# Clone the Tribler repo and install pip packages
RUN mkdir /tribler
COPY ./src /tribler/src
COPY ./experiment /tribler/experiment
# Install any experimental requirements
RUN pip3 install -r /tribler/experiment/requirements.txt
# Intall Tribler requirements
RUN pip3 install -r /tribler/src/requirements.txt && pip3 install -r /tribler/src/pyipv8/requirements.txt

# Expose ports
EXPOSE 7759
EXPOSE 8085

ENV PYTHONPATH="/tribler/src/pyipv8:/tribler/src/tribler-common:/tribler/src/tribler-core:/tribler"

# Define the command to run
CMD ["/usr/bin/python3", "/tribler/experiment/popularity_community/torrent_health.py"]