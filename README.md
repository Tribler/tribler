# Tribler

We make use of submodules, so remember using the --recursive argument when cloning this repo.

## Dependencies
TODO

## Running Tribler from this repository
### Unix
First clone the repository:

```bash
git clone --recursive  git@github.com:Tribler/tribler.git
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
