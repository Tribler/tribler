# Tribler - 1st Report

###Introduction

We are four students, attending "Software Engineering", a subject from the Master in Informatics and Computing Engineering at the Faculty of Engineering from University of Porto, currently analysing this open source project.

_Tribler_ is a **Peer-to-Peer file sharing program** that uses a dedicated **Tor-like network** for anonymous torrent downloading. The aim of this project is giving anonymous access to online (streaming) videos, trying to make privacy, strong cryptography and authentication the Internet norm.

****

###Activity
######18/09/2005 - 03/10/2015
_Tribler_ currently has **10.912 commits** and **28 contributors**. As of last month, excluding merges, **6 authors** have pushed **3 commits** to devel and **25 commits** to all branches. On devel, **2 files** have changed and there have been **0 additions** and **1 deletions**.

****

###Development process

As of today (03/10/2015), we weren't able to get a reply from the main contributors regarding the development process used in this project. Based on the existing processes and the project at hand, we chose what was, in our opinion, the most adequate development process for this specific project, the **Iterative and Incremental Development**.

The basic idea behind this method is to develop a system through repeated cycles (iterative) and in smaller portions at a time (incremental), allowing software developers to take advantage of what was learned during development of earlier parts or versions of the system, what makes this method great for the development of an open source project with a large number of contributors like _Tribler_.

####Advantages

* The cost of accommodating changing customer requirements is reduced.
  * There's less documentation to be changed
  * Unstable requirements can be left to later stages of development
* Generates working software quickly and early during the software life cycle which provides more frequent and early customer feedback.
* Customer value can be delivered with each increment so system functionality is available earlier.
* Early increments act as a prototype to help elicit requirements for later increments.
* Easier to test and debug during a smaller iteration.
* Lower risk of overall project failure.
* Easier to manage risk since risky pieces are identified and dealt with during its iteration.
* Each iteration is an easily managed milestone.
* The highest priority system services tend to receive the most testing.

####Disadvantages

* System **structure** tends to **degrade** as new increments are added.
  * Unless some time and money is spent on **refactoring** to improve the software, regular change tends to corrupt its structure. Incorporating further software changes becomes increasingly difficult and costly.
* It can be hard to identify upfront common facilities that are needed by all increments, so level of **reuse** may be suboptimal.
* Incremental delivery may not be possible for **replacement systems** as increments have less functionality than the system being replaced.
* The nature of incremental development of the specification together with the software may not be adequate for establishing a development contract at the beginning.

It seems to us this is an excelent model for an open-source project since the golden rule seems to be _Release often, release early_. For a project with various contributors this looks like a good way to manage the project because it allows for fast releases once a new increment is concluded.
