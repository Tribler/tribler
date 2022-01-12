# The base image already builds the libtorrent dependency so only Python pip packages
# are necessary to be installed to run Tribler core process.
FROM triblercore/libtorrent:1.2.10-x

# Update the base system and install required libsodium and Python pip
RUN apt update && apt upgrade -y
RUN apt install -y libsodium23 python3-pip git

# Then, install pip dependencies so that it can be cached and does not
# need to be built every time the source code changes.
# This reduces the docker build time.
RUN mkdir /requirements
COPY ./src/pyipv8/requirements.txt /requirements/pyipv8-requirements.txt
RUN pip3 install -r /requirements/pyipv8-requirements.txt

COPY ./src/tribler-common/tribler_common/requirements.txt /requirements/common-requirements.txt
RUN pip3 install -r /requirements/common-requirements.txt

COPY ./src/tribler-core/tribler_core/requirements.txt /requirements/core-requirements.txt
RUN pip3 install -r /requirements/core-requirements.txt

# Copy the source code and set the working directory
COPY ./ /tribler
WORKDIR /tribler

# Set the REST API port and expose it
ENV CORE_API_PORT=52194
EXPOSE 52194

# Only run the core process with --core switch
CMD ["./src/tribler.sh", "--core"]
