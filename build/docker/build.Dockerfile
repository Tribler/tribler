# libtorrent-2.0.9 does not support python 3.11 yet
FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libsodium23=1.0.18-1 \
    && rm -rf /var/lib/apt/lists/*

# Install Xvfb for headless GUI
RUN apt-get update -y \
  && apt-get -y install \
    xvfb nodejs npm git \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Set up a user in the container
RUN useradd -ms /bin/bash --home-dir /home/user user
USER user

# Clone the repository with arguments
ARG GIT_REPO=${GIT_REPO:-"https://github.com/tribler/tribler.git"}
ARG GIT_BRANCH=${GIT_BRANCH:-"main"}
RUN echo "Cloning $GIT_REPO on branch $GIT_BRANCH"
RUN git clone --recursive --branch "$GIT_BRANCH" "$GIT_REPO" /home/user/tribler

# Install NPM dependencies
WORKDIR /home/user/tribler/src/tribler/ui
RUN npm install \
    && npm run build

# Install Python dependencies
WORKDIR /home/user/tribler
RUN pip3 install -r requirements.txt

# Set IPv8 on pythonpath
ENV PYTHONPATH=pyipv8

# Run the application using Xvfb
CMD xvfb-run python3 src/run_tribler.py
