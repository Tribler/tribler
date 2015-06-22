# Generate pylint report
pylint -f parseable ../tsap/service/ | tee pylint.out
sed -i s#.*workspace/## pylint.out

# Clean test venv
rm -rf runtests

# Setup test venv
virtualenv --system-site-packages runtests
. runtests/bin/activate
pip install pytest
pip install nose -I
deactivate

# Generate nose test report
. runtests/bin/activate
echo Using nose from `which nosetests`
sleep 30
nosetests -v --with-xunit *_test.py
deactivate

# Cleanup
rm -rf runtests
