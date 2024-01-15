=======================================
Agreements Made Among Developers
=======================================

To add a change to this document, approval from all current developers is mandatory.
The current developers are listed here: https://github.com/orgs/Tribler/teams/reviewers

Agreements
==========

Branching Model
---------------
We use the OneFlow branching model, as detailed here: https://www.endoflineblog.com/oneflow-a-git-branching-model-and-workflow

We prefer the fork-centric workflow over the branch-centric workflow.

For the main branch, we use the name `main`.

For merging forks, we use: `rebase + merge --no-ff`

.. image:: https://www.endoflineblog.com/img/oneflow/feature-branch-rebase-and-merge-final.png
   :width: 600

Related issues:
 - https://github.com/Tribler/tribler/issues/5569
 - https://github.com/Tribler/tribler/issues/5575