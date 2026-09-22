## Security contact information

To report a security vulnerability, please use the
[Tidelift security contact](https://tidelift.com/security).
Tidelift will coordinate the fix and disclosure.

## Security supported versions

Automat is a [CalVer](https://calver.org) project that issues time-based
releases.  This means its version format is `YEAR.MONTH.PATCH`.

Users are expected to upgrade in a timely manner when new releases of automat
are issued; within about 3 months, so that we do not need to maintain an
arbitrarily large legacy support window for old versions.  This means that a
version is “current” until 3 months after the last day of the `YEAR.MONTH` of
the *next* released version.  This means at least one version is always
“current”, regardless of how long ago it was released.

The simple rule is this: **upgrade within 3 months of a release, and your
current version will always be security-supported**.

Automat releases are also largely intended to be compatible, following
[Twisted's compatibility
policy](https://docs.twisted.org/en/stable/development/compatibility-policy.html)
of R+2 for any removals.

Thus, “security support” is a function of breaking changes and time.  If a
vulnerability is discovered, all versions that were *current on that date* will
receive a security update.  A “security update” is a release with no removals
from its previous version, and thus will be installable without breaking
compatibility.

Some examples may be helpful to understand the nuances here.

Let's say it's August 9, 2027.  A vulnerability, V1, is discovered, that
affects many versions of automat.  The previous two versions of Automat were
2025.5.0 and 2026.1.0.  Because it is more than 3 months after january 2026,
only 2026.1.0 is current.  Thus, a security update of 2026.1.1 will be issued.

Alternately, let's say it's December 5th, 2029.  Another vulnerability, V2, is
discovered.  It's been an active year for automat: there were lots of
deprecations in 2028, and there has been a removal (a breaking change) in every
release in 2029, of which there has been one every month.  This means that
`2029.9.0`, `2029.10.0`, and `2029.11.0` will all be receiving `.1` security
updates, with no changes besides the security patch.

Once again, just upgrade within 3 months of a release, and you will have no
issues.
