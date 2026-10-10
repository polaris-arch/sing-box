# Fixed Cronet source and notice recovery

This slice adds review material only. It does not change producer behavior,
source inputs, package membership, licenseClosure, or publicationEligible.
The six-native producer remains pinned to source a01da7a942b3a0dbbfdfda2bba5bd63d5bd9d932
and its independently reviewed workflow revision for review is 720ead161c71415e23f38a82c29d314a4754ab9c,
including the Windows float/EOL fix and expected negative-error categories.
This materials-only branch is based on 756e2737 and is not a CI dispatch target;
its inherited workflow does not include the subsequent rejection-category fix.
The added source notice texts are candidates awaiting linkage review; they are
not a completed distributable notice bundle and are not included by the producer.

## Recovered original build lineage

The fixed library origin a1cafd93eb1f748f354378309f84de3e2d4a71e4 records
`Build from abcdebeb`. Its full source is abcdebebd23da6e74cf9c55ab63024ce66fc0f7b,
whose Naiveproxy Gitlink is be1be963131154ba82761a7ed85ba426b2027319.
[Official build run 36628634540](https://github.com/SagerNet/cronet-go/actions/runs/36628634540)
has that exact source head. Its workflow Git blob is
111a69ef1985b39ca6c4dd8f9d2658c460d1e618. The publish log records both
the a1cafd9 library commit and the 4d18a60 generated wrapper commit.

The 13 selected official artifacts were downloaded and their GitHub SHA256
digests verified. Every selected library matches both the candidate input byte
SHA256 and Git blob. The receipt binds each target to its artifact ID, module
origin/sum, exact library bytes, fixed source, and sanitized original build lines.
All 13 artifacts contain library/include/Go files but no LICENSE/NOTICE, generated
GN arguments, Ninja graph, link map, build receipt, attestation or SBOM.
This recovered upstream run does not validate our new Polaris candidate.

## Exact source availability

The fixed Naiveproxy public tree is nontruncated (43,361 entries, 35,452 blobs,
no Gitlinks). All tracked blobs are available in its official source tarball,
but GitHub applies CRLF conversion to 30 zstd Windows project files. The original
archive is retained with its actual SHA256 and the 30 mismatches in the receipt.
A separate derived archive restores LF only where the resulting bytes match the
expected Git blob. Every tracked blob and mode then matches the fixed source.
The receipt explicitly marks that archive as derived, not an official download.

The original Cronet build-driver tarball matches all 133 tracked blobs and modes.
Its separate Naiveproxy Gitlink is supplied by the verified source above.
Large source archives, binary artifact ZIPs and raw CI logs stay outside this Git
slice; their exact hashes, availability and public pinned download URLs are
recorded. Source archive bytes may need to be retained beside an eventual
distribution because GitHub artifact/download retention is not a durable source
delivery promise. These two archives cover the Cronet driver and Naiveproxy,
not the complete Corresponding Source of a distributed Polaris kernel.

## Candidate notices

71 fixed-source license/notice/copyright and README metadata files were recovered
across the entire curated repository, including nested third_party directories
in base, partition_allocator, net and url. All are copied without text edits and
bound to source path, Git blob and SHA256 in polaris-cronet-materials.json.
All 32 explicit README License File references resolve to recovered, verified
texts. Python license utilities and empty test metadata are excluded from this
filename selection. Shipped fields remain original metadata; they do not prove
which components are linked into any selected binary. Inline source-header
licenses can require additional handling after the actual dependency graph is
known. Missing standalone files in a curated component are not by themselves
evidence that its code is linked or that its licensing is defective.

The curated tree lacks generic tools/licenses/licenses.py. It does contain
components/cronet/license/create_android_metadata_license.py, but its default
targets are Android package/gn2bp targets, not this build driver's cronet and
cronet_static library targets. It must not be run unchanged and its output
presented as the matching notice bundle for these 13 libraries.

## Remaining acceptance work

The fixed build driver generates GN arguments and builds cronet on Windows,
cronet_static on other systems, and an additional cronet shared target on glibc
Linux. Per-platform options and the downloader scripts are present in the fixed
source. The original logs identify Go 1.26.8, Clang
llvmorg-24-init-3796-g20e97c4b-27 and Android native library NDK r24. These are
different from planned Polaris Go 1.25.5 and are not evidence for a current
gomobile or final-carrier NDK version. Global tools have not been changed.

Before distribution, bind a reviewed notice inventory to each actual
cronet/cronet_static dependency graph, including inline and nested notices.
Recover or reconstruct exact GN/Ninja/link-input metadata with a verifiable
relationship to each existing official library hash. Complete the external
tool/runtime, NDK/sysroot, SDK and PGO input content/source/notice receipts needed
for the source and build handoff; restored caches and version labels do not
supply those bytes. Assemble the complete required kernel/dependency source and
build instructions at the fixed distributed source.

After independent review, run the six hosted native CLI gates once with the
reviewed producer SHA. Final Android AAR and Apple libbox carriers require a
separate producer and final-link/load/byte checks; the existing seven Cronet
mobile archives alone are not those deliverables. No CI is dispatched by this
material recovery, no tag is created, and publicationEligible remains false.
