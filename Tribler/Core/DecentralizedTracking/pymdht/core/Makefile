

all: Makefile *.py
	rm .coverage *.pyc;\
	python doctest_all.py
	nosetests \
	--with-coverage --cover-package=pymdht.core #\
#	--pdb --pdb-failures #\
#	--with-doctest
