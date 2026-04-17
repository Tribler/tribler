cd ../../dist/
tar czf tribler.tar.gz tribler
cd ../build/alpine
mv ../../dist/tribler.tar.gz tribler.tar.gz
echo "pkgver=${GITHUB_TAG}" >> APKBUILD
echo "pkgrel=${GITHUB_BUILD_NUMBER}" >> APKBUILD
echo "sha512sums=\"$(sha512sum tribler.tar.gz)\"" >> APKBUILD
sudo addgroup runner abuild
abuild-keygen -a -i -n
mkdir -p packages
export REPODEST packages
sg abuild -c "abuild -r"
