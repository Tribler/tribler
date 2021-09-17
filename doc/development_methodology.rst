Branching model and development methodology
===========================================

In this post we'll explain the branching model and development methodology we use at `TUDelft <http://www.ewi.tudelft.nl/en/>`_ on the `Tribler <https://github.com/Tribler/tribler>`_ project.

This is mostly targeted at new developers joining the team. However, it may give you some useful ideas if you are working on a similar project type.

Branching model
---------------

Our branching model follows the `OneFlow <https://www.endoflineblog.com/oneflow-a-git-branching-model-and-workflow>`_ model.

Release lifecycle
-----------------

We follow `SemVer <https://semver.org/>`_ notation for release naming:

* Stable release name: <MAJOR>.<MINOR>.<PATCH>
* Release candidate name: <MAJOR>.<MINOR>.<PATCH>-RC<NUMBER>

We have to create a new branch For every MAJOR or MINOR release.

Therefore the following structure of the branch name is used: "release/<MAJOR>.<MINOR>".

Example: "release/7.8"

The release lifecycle:

1. A release branch forks from `main`.
2. The release branch is checked by running the application-tester
3. In case no errors, a release candidate (RC) is published as pre-release in Github and published to the forum as release post.
4. After a while (1-2 weeks), if there are no critical bugs, the release candidate is considered stable and ready for stable release.
5. A stable release tag is created and the release is published in Github. A forum post is created to inform the users in the forum.
6. The release branch is merged to `main`


In case of an error that needs to be fixed asap in the published stable release:

1. A fix is committed to the corresponding release branch
2. The release branch is checked by running the application-tester
3. The fixed release is delivered to users
4. The release branch is merged to `main`


A release is started by forking from the top of **main**.
From that moment, all the bugfixes relevant to the current release must be merged into the corresponding release branch.
No new features could be added to it.

When the release is ready for publishing, it is merged back to **main** to integrate the bugfixes.

Tags
----

Every revision that will result in a (pre)release gets tagged with a version number.

Setting up the local repo
-------------------------

To setting up the local repo, please follow to instructions `here <https://github.com/Tribler/tribler/tree/main/doc/development>`_.

Working on new features or fixes
--------------------------------

1. Make sure there's an issue for it and get it assigned to you. If there isn't, create it yourself. Otherwise you risk your changes not getting accepted upstream or wasting time on changes that are already being worked on by other developers.
2. Create your feature or bugfix branch. New feature branches can be created like this:

.. code-block:: none

   git fetch --all && git checkout upstream/main -b fix/2344_my_new_feature

For bug fixes:

.. code-block:: none

   git fetch --all && git checkout upstream/release/X.Y -b fix/2344_my_new_bugfix

2344 would be the issue number this branch is dealing with. This makes it trivial to identify the purpose of a branch if one hasn't had been able to work on it for a while and can't remember right away.

3. Create a `Pull Request <https://github.com/Tribler/tribler/compare>`_.

It is usually a good idea to create a pull request for a branch even if it's a work in progress. Doing so will make our `Jenkins instance <https://jenkins-ci.tribler.org>`_ run all the checks, tests and experiments every time you push a change so you can have continuous feedback on the state of your branch.

When creating a PR, always prepend the PR title with **WIP** until it's ready for the final round of reviews. More about this on the next section.

**Notes:**

- Always fork directly from upstream's remote branches as opposed to your own (remote or local) **main** or **release/** branches. Those are useless as they will quickly get out of date, so kill them with fire:

.. code-block:: none

  git branch -d release/X.Y
  git branch -d main

- Once one of your branches has been merged upstream try to always delete them from your remote to avoid cluttering other people's remote listings (I've got around 15 remotes on my local Tribler repos and it can become annoying to look for a particular branch among dozens and dozens of other people's stale branches). This can be done either from github's PR web interface by clicking on the "delete branch" button after the merge has been done or with:

.. code-block:: none

  git push MrStudent :fix/2344_my_new_bugfix

Getting your changes merged upstream
------------------------------------

When you think your PR is complete you need to get at least one peer to review your proposed changes as many times as necessary until it's ready. If you can't agree on something add another peer to the discussion to break the tie or talk to the lead developer.

All updates during the review/fix iteration cycles should be made with fixup commits to make it easier for the reviewer(s) to spot the new changes that need review on each iteration. (read the ``--fixup`` argument on the git-commit manpage if you don't know what a fixup commit is).

Once the reviewer gives the OK and the tests and checks are passing, the fixup commits can then be squashed and the **WIP** prefix can be switched to **READY**. The lead developer will then do the final review round.

As mentioned before, any requested modifications should come in the form of fixup commits to ease reviewing.

Once the final OK is given, all fixup commits should be squashed and the branch will get merged.

Submodule notes
---------------

- As updated submodules are in detached head state, remember to check out a branch before committing changes on them.
- If you forgot to check out a branch before doing a commit, you should get a warning telling you about it. To get the commit to a branch just check out the branch and do a git cherry-pick of the commit.
- Take care of not accidentally committing a submodule revision change with ``git commit -a``.
- Do not commit a submodule update without running all the tests first and making sure the new code is not breaking Tribler.


Misc guidelines
---------------

- **Keep an eye on the PRs you've reviewed**
    You will probably learn something from other reviewers and find out what you missed out during yours.
- **Don't send PR from your remote's ~main~ branch**
    Use proper names for your branches. It will be more informative and they become part of the merge commit message.
- **Keep it small**
    The smaller the PRs are, the less review cycles will be needed and the quicker they will get merged.
- **Try to write as many tests as you can before writing any code**
    It will help you think about the problem you are trying to solve and it usually helps to write code that's easier to test.
- **Have the right amount of commits on your PRs**
    Don't have a feature implementation spread across a gazillion commits. For instance if a given feature requires some refactoring, your history could look like this:

    - "Refactor foo class to allow for bar" (At this point, the code should still work)
    - "Tests for feature $X"
    - "Implement feature $X"
- **Write clean and self contained commits**
    Each commit should make sense and be reviewable by itself. It doesn't make sense to break something on one commit and fix it on another later on in the same PR. It also makes reviews much harder.
- **Avoid unrelated and/or unnecessary modifications**
    If you are fixing a bug or implementing a feature, avoid unnecessary refactoring, white space changes, cosmetic code reordering, etc. It will introduce gratuitous merge conflicts to your and others' branches and make it harder to track changes (for instance with git blame).
- **Don't rename a file and modify it on the same commit**
    If you need to rename and modify a file on the same PR, do so in two commits. This way git will always know what's going on and it will be easier to track changes across file renames.
- **Don't send pull requests with merge commits on them**
    Always rebase or cherry pick. If a commit on **main** introduces merge conflicts in your branch, fix your commits by rebasing not by back merging and creating a conflict resolution commit.
- **If one of your commits fixes an issue, mention it**
    Add a "Closes #1234" line to the comment's body section (from line 3 onwards). This way a reference to this particular commit will be created on the issue itself and once the commit hits the target branch the issue will be closed automatically. If a whole PR is needed to close a particular issue, add the "Closes" comment on the PR body.
- **Capitalize the commit's subject**
    We are civilized people after all :D
- **Write concise commit messages**
    If a particular commit deserves a longer explanation, write a short commit message, leave a blank line after it and then go all Shakespeare from the third line (message body) onwards.
- **Read** `this <http://chris.beams.io/posts/git-commit>`_
    Really, do it.
