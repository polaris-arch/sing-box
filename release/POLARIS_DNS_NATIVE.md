# DNS-01 fixed four-core technical batch

The product source stays aafc521b745e0d1a8f50a6a3f41169433f1c2194,
tree 4ae424d8a99b16a02442d7b2eac1d5e24e938d8e. Producer changes accumulate
on collab/windows-auto-route-dns-compat-20261011; its frozen technical HEAD
is supplied explicitly and is distinct from the product source SHA.
No separate producer/material/review branches and no automatic CI are used.

Inputs are release/polaris-dns-candidate-inputs.json, byte-pinned by the producer.
The exact local sing-tun replacement is tree
18492017863a3bf41df92fe528c2bbe38fe97ab2, 256 files, based on upstream
5c2edb183cc92eb190d41c04dedfa5519ca3e78c. The exact source patch SHA256 is
812956b42cfbb5d302343998b898b9c6489a93f633b1f446c367c5c24681ecd1.
Version v0.9.7-0.20261009022811-5c2edb183cc9 identifies the original module;
its h1 sum authenticates the baseline ZIP, not the modified local replacement.
Full replacement tree/binding/patch and actual binary replacement records are
mandatory. Root go.mod/go.sum and both source helper hashes are pinned.

The existing registered polaris-native-candidate.yml path is used for a single
manual fixed-head run, four native jobs in sequence: Linux amd64, Windows amd64,
macOS amd64 and macOS arm64. No ARM Windows/Linux extra build is scheduled.
The two foreign libraries remain frozen download-only negative fixtures.
Go 1.25.5 is local/pinned, GOMAXPROCS=2 and build/test -p1; each Go call uses
the same isolated_go_environment factory as the approved source collector:
GOENV=off, GOWORK=off, GOFLAGS empty, GOTOOLCHAIN=local. Overrides for workspace,
overlay/modfile and external build directory are rejected. Compiler flags and
native architecture are explicit; macOS uses the already verified SDK flags.
Cronet libraries are downloaded at their exact original module/h1/blob/byte
identities. Linux/Windows use prebuilt so/dll; macOS links the prebuilt .a.
This workflow never rebuilds Chromium/Cronet or globally upgrades toolchains.

Each job freshly collects source identity and module JSON, runs the real Windows
DNS helper tests (including native Windows early guards), builds a new kernel,
measures real go version -m, go tool buildid and the binary's version output,
and rejects wrong/missing/extra replacements, old source revisions, dirty VCS,
wrong tags/arch/CGO/toolchain/BuildID/version. Cronet native smoke and categorized
negative tests, complete archive member readback and extracted native smoke
are retained from reviewed producer 83129008. All output is outside the clean
frozen source. Existing destinations and old binaries cannot be reused.

commonSourceIdentity is a canonical stable projection of source SHA/tree,
Go version, root go.mod/go.sum and exact replacement binding. Host-specific
absolute module cache paths, executable SHA and raw module JSON are separately
measured evidence, not a shared fingerprint. platformInputIdentity adds the
actual target/tags/CGO/version and determines a technical BuildID. Neither this
schema nor its BuildID is the App's polaris-desktop-core-v1 receipt.

release/polaris-dns-consumer-handoff.json states the exact consumer contract.
Observed consumer 35a496b8 still pins 052 and refuses replacements. App source
and core manifests, an immutable role-annotated source tag, final polaris.N
version/BuildID/signature policies and four actual output receipts must be
integrated by the consumer owner before admission. sourceTag and tagObject
remain null here; no guessed tag or hash, no old a01/052 binary relabeling.
Mobile alpha8 and public a01 release stay fixed. The old source-only release
must remain while the consumer still references it.

All produced receipts explicitly remain candidateOnly, publicationEligible=false,
AppAdmissible=false and realWindowsDNSAcceptance=false. Real OS/TUN/network,
mobile carrier final links, distribution trust and App full-config acceptance
are separate unverified boundaries. Whole-batch source review precedes the one
necessary native CI dispatch. No tags/releases/main/device writes occur here.

Pinned Go 1.25.5 requires a standalone source checkout with a real `.git` directory for VCS stamping. The producer rejects worktree gitfiles before downloading or building; the final binary must still carry the exact source SHA and `vcs.modified=false`.

Go 1.25.5 also stamps the root module pseudo-version from available Git tags. Only `v0.0.0-20261010200656-aafc521b745e` (untagged shallow CI) and `v1.15.0-alpha.11.0.20261010200656-aafc521b745e` (upstream alpha.11 ancestor present) are accepted. Both require actual `vcs=git`, full `aafc` revision, commit time `2026-10-10T20:06:56Z` and clean state. Observed root versions remain evidence; they do not replace the stable common source identity or application version.
