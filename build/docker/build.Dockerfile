# Build & run instructions:
# 1. docker build -f build/docker/build.Dockerfile .
# 2. docker run --security-opt "apparmor:unconfined" -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR -e DISPLAY=$DISPLAY -e XAUTHORITY=$XAUTHORITY -e CORE_API_PORT=8085 -e CORE_API_KEY="changeme" --net="host" -v ~/.Tribler:/state -v ~/downloads/TriblerDownloads:/downloads --env DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" -e XDG_CACHE_HOME=$XDG_CACHE_HOME -v $XDG_CACHE_HOME/tmp/:$XDG_CACHE_HOME/tmp/ -v /run:/run --user $(id -u):$(id -g) -e BROWSER="x-www-browser" -it <<HASH>>
#
# Common issue: "permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock"
#          fix: "sudo chmod 666 /var/run/docker.sock"

FROM ubuntu:latest

RUN apt update -y \
  && apt -y install curl dbus-x11 libgirepository-1.0-1 libcanberra-gtk-module libcanberra-gtk3-module libglib2.0-bin

RUN tag=`basename $(curl -Ls -o /dev/null -w %{url_effective} https://github.com/Tribler/tribler/releases/latest)` \
  && vlesstag=$(echo $tag | cut -c2-) \
  && echo "Tag with v = ${tag}, tag without v = ${vlesstag}" \
  && cd /home/ubuntu \
  && curl -LO "https://github.com/Tribler/tribler/releases/download/${tag}/tribler_${vlesstag}_x64.deb" \
  && apt install -y "./tribler_${vlesstag}_x64.deb" \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

SHELL ["/bin/bash", "-c"]
CMD export TMPDIR="${XDG_CACHE_HOME}"/tmp/ \
  && mkdir -p ~/custombin \
  && echo '#!/bin/bash' > ~/custombin/x-www-browser \
  && echo 'gdbus call --session --dest=org.freedesktop.portal.Desktop --object-path=/org/freedesktop/portal/desktop --method=org.freedesktop.portal.OpenURI.OpenURI "" "$1" "{}"' >> ~/custombin/x-www-browser \
  && chmod u+x ~/custombin/x-www-browser \
  && PATH=~/custombin:$PATH /usr/share/tribler/tribler
