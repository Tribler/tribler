

# How to contribute to the Tribler project? #

## Reporting bugs ##

* Make sure the issue/feature you want to report doesn't already exist.
* If you want to report more than one bug or feature, create individual issues for each of them.
* Use a clear descriptive title.
* Provide at least the following information:
    * The version of Tribler that you are using, if you are running from a branch, branch name and commit ID.
    * The OS and version you are running.
    * Step by step instructions to reproduce the issue in case it's a bug.
    * Attach Tribler's log file found in `%APPDATA%` on Windows or on
      `~/.Tribler/` on Linux/OSX (have a look at its contents before posting it
      in case you want to edit out something)
    * Does it still happen if you move `%APPDATA\.Tribler` away temporarily? (Do _not_ delete it!)
    * Do you have any other software installed that might interfere with Tribler?

## Pull requests ##

When creating a new Pull request, please observe the following:
  * Fixes go to `next`, features go to `devel`.
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
  * Do an `autopep8` pass before submiting the pull request.
  * Do a `pylint` pass with the `.pylintrc` on the root of the repository and
    make sure you are not raising the base branch violation count, it's bad enough as it is :).
  * For more PR etiquette have a look [here](https://github.com/blog/1943-how-to-write-the-perfect-pull-request)
