.. _contributing:

*****************************************
How to contribute to the Tribler project?
*****************************************

Checking out the Stabilization Branch
=====================================

The stabilization branch ``release-X.Y.Z`` contains the most up to date bugfixes. If your issue cannot be reproduced there, it is most likely already fixed.

To backup your Tribler installation and checkout the latest version of the stabilization branch, please perform the following steps.
* Copy the ``.Tribler`` folder to a safe location on your system (for instance the desktop) Make sure to leave the original folder on its original location. This folder is located at ``~/.Tribler/`` (Linux/OS X) or ``%APPDATA\.Tribler`` (Windows).
* Remove the ``tribler`` installation folder.
* Go to `the latest tested version of Tribler <https://jenkins-ci.tribler.org/job/Build-Tribler_release/job/Build/lastStableBuild/>`_ and under 'Build Artifacts', download the package appropriate to your operating system.
* Install/unzip this package.

To revert back to your original version of Tribler, `download the installer again <https://github.com/Tribler/tribler/releases>`_ and install it. Afterwards you can restore your backed up Tribler data folder.

Reporting bugs
==============

* Make sure the issue/feature you want to report doesn't already exist.
* If you want to report more than one bug or feature, create individual issues for each of them.
* Use a clear descriptive title.
* Provide at least the following information:
    * The version of Tribler that you are using, if you are running from a branch, branch name and commit ID.
    * The OS and version you are running.
    * Step by step instructions to reproduce the issue in case it's a bug.
* Attach Tribler's log file. On Windows, these are found in ``%APPDATA%``. On Linux distributions, the log file is located in ``~/.Tribler/``. On OS X, the crash logs can be found in ``~/Library/Logs/DiagnosticReports`` and logger output can be found in the ``syslog``. The location of this log is ``/var/log/system.log``. You can use the following command to extract Tribler-related lines from the syslog: ``syslog -C |grep -i tribler > ~/tribler.log``. Please have a look at the content of the log files before posting it in case you want to edit out something.
    * Does it still happen if you move ``%APPDATA%\.Tribler`` away temporarily? (Do **not** delete it!)
    * Do you have any other software installed that might interfere with Tribler?

Pull requests
=============

When creating a new Pull request, please observe the following:
  * New features always go to ``devel``.
  * If there is an unreleased ``release-X.Y.Z`` branch, fixes go there.
  * Otherwise, fixes go to ``devel``.
  * Before starting to work on a feature or fix, check that nobody else is
    working on it by assigning yourself the corresponding issue. Create one if it
    doesn't exist. This is also useful to get feedback about if a given feature
    would be accepted. If you are not a member of the project, just drop a
    comment saying that you are working on that.
  * Create one PR per feature/bugfix.
  * Provide tests for any new features/fixes you implement and make sure they
    cover all methods and at least the important branches in the new/updated
    code.
  * If implementing a reasonably big or experimental feature, make it toggleable
    if possible (For instance for a new community, new GUI stuff, etc.).
  * Keep a clean and nice git history:
      * Rebase instead of merging back from the base branch.
      * Squash fixup commits together.
      * Have nice and descriptive commit messages.
  * Do not commit extraneous/auto-generated files.
  * Use Unix style newlines for any new file created.
  * No print statements if it's not really justified (command line tools and such).
  * Do an ``autopep8`` pass before submitting the pull request.
  * Do a ``pylint`` pass with the ``.pylintrc`` on the root of the repository and
    make sure you are not raising the base branch violation count, it's bad enough as it is :).
  * For more PR etiquette have a look `here <https://github.com/blog/1943-how-to-write-the-perfect-pull-request>`_.
