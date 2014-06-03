# Tribler           [![Build Status](http://jenkins.tribler.org/job/Test_tribler_devel/badge/icon)](http://jenkins.tribler.org/job/Test_tribler_devel/)

We make use of submodules, so remember using the --recursive argument when cloning this repo.

## Dependencies

### Debian/Ubuntu/Mint
```sh
sudo apt-get install scons build-essential libevent-dev \
                     python-libtorrent python-apsw \
                     python-wxgtk2.8 python-netifaces \
                     python-m2crypto vlc python-igraph \
                     python-pyasn1 python-gmpy
```

### Fedora
You'll need to have the [rpmfusion] repos installed for vlc. only the rpmfusion-free repo is needed. This can be done by running the following command:
```sh
su -c 'yum localinstall --nogpgcheck http://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm -y'
```

The following packages are needed to run tribler on Fedora:
```sh
sudo yum group install "Development Tools" -y
sudo yum install scons libevent-devel python-apsw \
                 python-netifaces vlc python-igraph \
                 python-pyasn1 gmpy gmp-devel m2crypto \
                 rb_libtorrent-python wxPython \
                 python-devel python-twisted
```

### Windows
TODO

### OSX
TODO

## Running Tribler from this repository
### Unix
First clone the repository:

```bash
git clone --recursive  git@github.com:Tribler/tribler.git
```

or, if you don't have added your ssh key to your github account:

```bash
git clone --recursive  https://github.com/Tribler/tribler.git
```
Then build swift and copy the binary where Tribler expects it to be:

```bash
cd  tribler/Tribler/SwiftEngine
scons #or scons -j8 if you have 8 cores on your machine.
cp swift ../..
cd ../..
```

Done!
Now you can run tribler by executing the tribler.sh script on the root of the tree:

```bash
./tribler.sh
```
### Windows
TODO

# Submodule notes
 - As updated submodules are in detached head state, remember to check out a branch before commiting changes on them.
 - If you forgot to check out a branch before doing a commit, you should get a warning telling you about it. To get the commit to a branch just check out the branch and do a git cherry-pick of the commit.
 - Take care of not accidentally commiting a submodule change with git commit -a
 - Do not commit a submodule update without running all the tests first and making sure the new code is not breaking Tribler.

[rpmfusion]: http://rpmfusion.org/ "RPM Fusion"
