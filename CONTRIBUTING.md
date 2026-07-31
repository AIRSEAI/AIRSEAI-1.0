# Contributing to AIRSEAI

Thanks for your interest in contributing to AIRSEAI. This document explains the
requirements every contribution must meet before it can be merged.

## Developer Certificate of Origin (DCO)

AIRSEAI requires all contributors to sign off on their commits under the
[Developer Certificate of Origin 1.1](https://developercertificate.org/). The
sign-off is your statement that you have the right to submit the contribution
under the project's [Apache License 2.0](LICENSE).

The full text of the DCO is:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### How to sign off

Every commit must contain a `Signed-off-by` line in its message that matches the
commit author's real name and email address:

```
Signed-off-by: Jane Developer <jane@example.com>
```

Git adds this line automatically with the `-s` flag:

```bash
git commit -s -m "Add obstacle filter to navigation module"
```

Make sure your Git identity is configured first:

```bash
git config user.name "Jane Developer"
git config user.email "jane@example.com"
```

### Signing off automatically (GUI clients)

Graphical clients such as Sourcetree, GitKraken and the VS Code Git panel do not
pass the `-s` flag, so they produce unsigned commits by default. This repository
ships a Git hook that adds the trailer for you. Enable it once per clone:

```bash
git config core.hooksPath .githooks
```

From then on every commit made from any client — command line or GUI — is signed
off using your configured `user.name` and `user.email`.

### Fixing missing sign-offs

Pull requests are checked automatically, and any PR containing an unsigned
commit will be blocked until it is fixed.

Amend the most recent commit:

```bash
git commit --amend -s --no-edit
git push --force-with-lease
```

Sign off every commit on your branch (replace `main` with the base branch):

```bash
git rebase --signoff main
git push --force-with-lease
```

## Pull request process

1. Fork the repository and create a topic branch from `main`.
2. Keep each pull request focused on a single logical change.
3. Sign off every commit as described above.
4. Write a clear PR description explaining the motivation and the approach.
5. Ensure the affected modules still build and run before requesting review.
6. Address review feedback by pushing additional commits (also signed off);
   squashing is done at merge time.

## Reporting issues

Please open a GitHub issue and include the hardware and software configuration
you are using, the steps to reproduce, the expected behaviour, and the observed
behaviour. Relevant logs and configuration files help a great deal.

## License

By contributing to AIRSEAI, you agree that your contributions will be licensed
under the Apache License 2.0, as found in the [LICENSE](LICENSE) file.
