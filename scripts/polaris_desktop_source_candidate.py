"""Offline assembly of the frozen three-platform source/notice review candidate."""
import argparse
import gzip
import hashlib
import io
import json
import pathlib
import shutil
import tarfile
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_member(name):
    pure = pathlib.PurePosixPath(name)
    require(bool(name) and not pure.is_absolute() and '..' not in pure.parts
            and '\\' not in name and ':' not in name and str(pure) == name,
            'unsafe source package member: ' + repr(name))


def input_path(root, name):
    safe_member(name)
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), 'input escapes declared root: ' + name)
    return path


def check_file(path, record):
    require(path.is_file(), 'missing source input: ' + str(path))
    require(path.stat().st_size == record['bytes'], 'input size mismatch: ' + str(path))
    require(file_hash(path) == record['sha256'], 'input SHA256 mismatch: ' + str(path))


def add_bytes(archive, name, data, mode=0o644):
    safe_member(name)
    member = tarfile.TarInfo(name)
    member.size, member.mode, member.mtime = len(data), mode, 0
    member.uid = member.gid = 0
    archive.addfile(member, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=pathlib.Path, required=True)
    parser.add_argument('--stage-dir', type=pathlib.Path, required=True)
    parser.add_argument('--module-cache', type=pathlib.Path, required=True)
    parser.add_argument('--go-toolchain-zip', type=pathlib.Path, required=True)
    parser.add_argument('--output-dir', type=pathlib.Path)
    parser.add_argument('--validate-only', action='store_true')
    options = parser.parse_args()
    stage = options.stage_dir.resolve()
    closure = options.evidence_root.resolve() / 'cronet-license-closure'
    module_cache = options.module_cache.resolve()
    index = json.loads((stage / 'DESKTOP-SOURCE-NOTICE-INDEX-controlled.json').read_text())
    require(index['publicationEligible'] is False and
            index['packageNoticeInputsAdoptedByProducer'] is False,
            'this helper only accepts unpublished, unadopted review inputs')
    require(sum(row['nativeAccepted'] for row in index['platforms']) == 3,
            'this frozen assembly recipe only covers three original platforms')
    notice = input_path(stage, 'DESKTOP-SOURCE-NOTICE-SUPERSET.txt')
    raw = notice.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == index['noticeBundle']['sha256'],
            'notice bundle SHA256 mismatch')
    for record in index['noticeRecords']:
        offset, length = record['byteOffset'], record['bytes']
        require(isinstance(offset, int) and isinstance(length, int) and offset >= 0 and length >= 0,
                'invalid notice slice')
        data = raw[offset:offset + length]
        require(len(data) == length and hashlib.sha256(data).hexdigest() == record['sha256'],
                'notice slice SHA256 mismatch')
    sources = []
    for record in index['sourceArchiveInputs']:
        path = input_path(closure, record['filename'])
        check_file(path, record)
        sources.append(('sources/' + record['filename'], path, dict(record)))
    sources.append(('notices/DESKTOP-SOURCE-NOTICE-SUPERSET.txt', notice, dict(index['noticeBundle'])))
    for record in index['buildRecipeInputs'] + index['sourceAssemblyInputs']:
        path = input_path(stage, record['path'])
        check_file(path, record)
        sources.append((record['path'], path, dict(record)))
    for module in index['modules']:
        name = module['sourceBundleMember']
        if name is None:
            continue
        safe_member(name)
        require(name.startswith('modules/'), 'invalid module source member')
        path = input_path(module_cache, name.removeprefix('modules/'))
        expected = {'bytes': module['zipBytes'], 'sha256': module['zipSha256']}
        check_file(path, expected)
        sources.append((name, path, expected))
    toolchain = options.go_toolchain_zip.resolve()
    require(file_hash(toolchain) == index['localGoToolchainInput']['zipSha256'],
            'Go toolchain source ZIP SHA256 mismatch')
    names = [name for name, _, _ in sources]
    require(len(names) == len(set(names)), 'duplicate source input member')
    if options.validate_only:
        print(json.dumps({'inputValidation': 'passed', 'modules': len(index['modules']),
                          'rawNoticeSlices': len(index['noticeRecords']),
                          'archiveInputs': len(index['sourceArchiveInputs']),
                          'recipeInputs': len(index['buildRecipeInputs']),
                          'assemblyInputs': len(index['sourceAssemblyInputs']),
                          'publicationEligible': False}))
        return
    require(options.output_dir is not None, '--output-dir required for assembly')
    output_dir = options.output_dir.resolve()
    require(not output_dir.exists(), 'use a fresh output directory; preserve previous candidate bytes')
    output_dir.mkdir(parents=True, mode=0o700)
    toolchain_snapshot = output_dir / 'verified-go-toolchain-input.zip'
    with toolchain.open('rb') as original, toolchain_snapshot.open('xb') as snapshot:
        shutil.copyfileobj(original, snapshot)
    require(file_hash(toolchain_snapshot) == index['localGoToolchainInput']['zipSha256'],
            'verified Go toolchain snapshot SHA256 mismatch')
    stdlib = output_dir / 'go1.25.5-standard-library-source-v2.tar.gz'
    count = 0
    with stdlib.open('xb') as stream, gzip.GzipFile(fileobj=stream, mode='wb', mtime=0, compresslevel=1) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive, zipfile.ZipFile(toolchain_snapshot) as source:
            prefix = next(name.split('/src/')[0] + '/' for name in source.namelist() if '/src/' in name)
            for name in sorted(source.namelist()):
                relative = name.removeprefix(prefix)
                if (relative.startswith('src/') or relative in ('LICENSE', 'PATENTS', 'VERSION')) and not name.endswith('/'):
                    mode = (source.getinfo(name).external_attr >> 16) & 0o777
                    add_bytes(archive, 'go1.25.5/' + relative, source.read(name), mode or 0o644)
                    count += 1
    toolchain_snapshot.unlink()
    stdlib_expected = {'bytes': stdlib.stat().st_size, 'sha256': file_hash(stdlib)}
    sources.append(('sources/' + stdlib.name, stdlib, stdlib_expected))
    portable = dict(index)
    portable.update(completeCorrespondingSource=False, completeThirdPartyNotices=False,
                    standardLibrarySource={'version': 'go1.25.5', 'fileCount': count,
                                          'derivedFromToolchainZipSha256': index['localGoToolchainInput']['zipSha256'],
                                          'sourceArchiveSha256': stdlib_expected['sha256']},
                    sourcePackageMembers=[{'path': name, 'bytes': expected['bytes'], 'sha256': expected['sha256']} for name, _, expected in sources])
    index_bytes = (json.dumps(portable, indent=2) + '\n').encode()
    readme = b'''Polaris a01 desktop source/notice review candidate: three original platforms.

This is the Linux amd64/arm64 and Windows amd64 source union from producer720ead
run38072592310. It does not cover all six successful native jobs. Old receipts
retain their actual producer/source identities; producer226e88 recipes supply
reviewed build instructions and never relabel the old bytes.

Sources include fixed kernel,147 Go source module ZIPs, Go1.25.5 standard-library
source, original Cronet driver and original plus explicitly Git-byte-restored
Naiveproxy source. Original exported CRLF differences are retained separately.
The curated compiler-rt atomic patch remains in that source.264 notice slices
preserve their raw source bytes, offsets and hashes. This is a conservative
notice candidate and metadata reconstruction, not an original link map or a
legal compliance guarantee. Compiler/SDK/PGO binary reproducibility is separate
from applicable shipped-code/runtime source and notice obligations.

Follow exact tags/flags/commands and frozen library identities in the receipts.
Download the pinned existing Cronet .so/.dll/.a; build only the Go kernel.
macOS links the supplied .a. No Chromium rebuild or global tool upgrade occurs.
Binary-acquisition module ZIPs are indexed, not labelled Chromium source.

Current native archives have not adopted these notice inputs. Controlled input
review, six-platform delta inclusion, final archive receipts and stable public
source delivery remain pending. publicationEligible is false.
'''
    checksums = [(expected['sha256'], name) for name, _, expected in sources]
    checksums += [(hashlib.sha256(index_bytes).hexdigest(), 'SOURCE-INDEX.json'),
                  (hashlib.sha256(readme).hexdigest(), 'README.txt')]
    sum_bytes = ''.join(digest + '  ' + name + '\n' for digest, name in sorted(checksums, key=lambda row: row[1])).encode()
    bundle = output_dir / 'polaris-box-a01-desktop-source-candidate-three-platforms-v3.tar.gz'
    pending = bundle.with_name(bundle.name + '.pending')
    with pending.open('xb') as stream, gzip.GzipFile(filename=bundle.name, fileobj=stream, mode='wb', mtime=0, compresslevel=1) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, path, expected in sorted(sources):
                safe_member(name)
                member = tarfile.TarInfo(name)
                member.size, member.mode, member.mtime = expected['bytes'], 0o644, 0
                with path.open('rb') as file_stream:
                    archive.addfile(member, file_stream)
            add_bytes(archive, 'SOURCE-INDEX.json', index_bytes)
            add_bytes(archive, 'README.txt', readme)
            add_bytes(archive, 'SHA256SUMS', sum_bytes)
    require(pending.stat().st_size < 300_000_000, 'source candidate exceeds bounded size')
    with tarfile.open(pending) as archive:
        members = archive.getmembers()
        require(len(members) == len({m.name for m in members}) == len(sources) + 3,
                'archive member count or uniqueness mismatch')
        for member in members:
            safe_member(member.name)
            require(member.isfile(), 'unexpected non-file source package member')
        require(archive.extractfile('SHA256SUMS').read() == sum_bytes,
                'packaged checksum manifest differs from frozen expected hashes')
        expected_members = {name: {'bytes': expected['bytes'], 'sha256': expected['sha256']}
                            for name, _, expected in sources}
        for name, data in [('SOURCE-INDEX.json', index_bytes), ('README.txt', readme), ('SHA256SUMS', sum_bytes)]:
            expected_members[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        require(set(archive.getnames()) == set(expected_members), 'archive expected member set mismatch')
        for name, expected in expected_members.items():
            require(archive.getmember(name).size == expected['bytes'], 'packaged member size mismatch: ' + name)
            with archive.extractfile(name) as member_stream:
                require(hashlib.file_digest(member_stream, 'sha256').hexdigest() == expected['sha256'],
                        'packaged member differs from frozen expected SHA256: ' + name)
    pending.rename(bundle)
    record = {'filename': bundle.name, 'bytes': bundle.stat().st_size, 'sha256': file_hash(bundle),
              'verifiedMemberCount': len(sources) + 3,
              'sourceModuleZipCount': sum(bool(m['sourceBundleMember']) for m in index['modules']),
              'productSourceCommit': index['sourceCommit'], 'actualAcceptedPlatformCount': 3,
              'completeSixTargetSource': False, 'noticeInputsAdoptedByNativeProducer': False,
              'publicSourceDeliveryPerformed': False, 'publicationEligible': False}
    (output_dir / 'bounded-source-package-receipt-v3.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
