# Build & run instructions:
# 1. docker build -f build/docker/build.Dockerfile .
# 2.a. docker run -e CORE_API_PORT=8085 -e CORE_API_KEY="changeme" -v ~/.Tribler:/state -v ~/downloads/TriblerDownloads:/downloads -v $XDG_CACHE_HOME/tmp:/hosttmp -v /run:/run --security-opt "apparmor:unconfined" --net="host" -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR -e DISPLAY=$DISPLAY -e XDG_CACHE_HOME=$XDG_CACHE_HOME -e XAUTHORITY=$XAUTHORITY -e DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" --user $(id -u):$(id -g) -it <<HASH>>
# 2.b. docker run -e CORE_API_PORT=8085 -e CORE_API_KEY="changeme" -v ~/.Tribler:/state -v ~/downloads/TriblerDownloads:/downloads --net="host" -it <<HASH>> -s
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
RUN mkdir -p /home/ubuntu/custombin \
  && echo '#!/bin/bash' > /home/ubuntu/custombin/x-www-browser \
  && echo 'gdbus call --session --dest=org.freedesktop.portal.Desktop --object-path=/org/freedesktop/portal/desktop --method=org.freedesktop.portal.OpenURI.OpenURI "" "$1" "{}"' >> /home/ubuntu/custombin/x-www-browser \
  && chmod 777 /home/ubuntu/custombin/x-www-browser

# This is supposed to give icons on Xorg systems, but it doesn't seem to always work.
ENV TMPDIR="/hosttmp/"

ENV PATH="/home/ubuntu/custombin:$PATH"
ENV BROWSER="x-www-browser"

ENTRYPOINT ["/usr/share/tribler/tribler"]
