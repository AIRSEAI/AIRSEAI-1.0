# Publication Release Policy

For a paper or archival citation, do not cite only the moving `main` branch.
After this artifact PR is merged and the fresh-clone CI passes:

1. record the exact merge commit SHA;
2. create an immutable release tag (recommended: `embodicore-cal-v1.0`);
3. rerun `airseai_embodicore/scripts/verify_release.sh` at that tag;
4. cite the tag or exact commit in the manuscript/artifact statement.

The release tag should be created only after the final artifact tree and
`MANIFEST.sha256` are frozen.
