if [[ ! -f "snap/snapcraft.yaml" ]]; then
    echo "snap/snapcraft.yaml does not exist in $PWD. Please make sure to execute the script from build/debian directory."
    exit 1
fi

# Make sure we have the latest packages
apt-get update

BUILD_ARGS=${SNAP_BUILD_ARGS:-''}
snapcraft $BUILD_ARGS

# Remove intermediate files
rm -rf parts stage prime

# Make sure the snap package is accessible.
# Especially useful when building in docker.
chmod 777 ./*.snap