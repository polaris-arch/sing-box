import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from polaris_native_candidate import archive_members, package, required_cronet_symbols, verify_required_exports


class CandidateArchiveTests(unittest.TestCase):
    def test_exact_payload_roundtrip_in_both_archive_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / 'polaris-box-candidate-linux-amd64'
            (root / 'licenses').mkdir(parents=True)
            (root / 'sing-box').write_bytes(b'kernel\x00bytes')
            (root / 'libcronet.so').write_bytes(b'library\x00bytes')
            (root / 'licenses/NOTICE').write_text('exact notice')
            for os_name, suffix in [('linux', '.tar.gz'), ('windows', '.zip')]:
                with self.subTest(os=os_name):
                    members = package(root, base / ('candidate' + suffix), os_name)
                    self.assertEqual(members[root.name + '/sing-box'], b'kernel\x00bytes')
                    self.assertEqual(len(members), 3)

    def test_tar_rejects_traversal_links_duplicate_and_multiple_roots(self):
        for names, link in [(['root/../escape'], None), (['root/link'], tarfile.SYMTYPE),
                            (['root/link'], tarfile.LNKTYPE), (['root/x', 'root/x'], None),
                            (['one/x', 'two/x'], None)]:
            with self.subTest(names=names, link=link), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'candidate.tar.gz'
                with tarfile.open(path, 'w:gz') as writer:
                    for name in names:
                        entry = tarfile.TarInfo(name)
                        if link:
                            entry.type = link
                            entry.linkname = '/outside'
                            writer.addfile(entry)
                        else:
                            entry.size = 1
                            writer.addfile(entry, io.BytesIO(b'x'))
                with self.assertRaises(ValueError):
                    archive_members(path)

    def test_zip_rejects_windows_paths_and_symlinks(self):
        for name, mode in [('root/../escape', 0), ('C:/escape', 0),
                           ('root\\escape', 0), ('root/link', 0o120777)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'candidate.zip'
                with zipfile.ZipFile(path, 'w') as writer:
                    entry = zipfile.ZipInfo(name)
                    entry.external_attr = mode << 16
                    writer.writestr(entry, b'/outside')
                with self.assertRaises(ValueError):
                    archive_members(path)


class CronetRequiredExportsTests(unittest.TestCase):
    def test_windows_64_bit_float_exports_are_required(self):
        core = 'Cronet_Engine_Create'
        floats = ['Cronet_EngineParams_network_thread_priority_set',
                  'Cronet_EngineParams_network_thread_priority_get']
        with tempfile.TemporaryDirectory() as directory:
            wrapper = Path(directory)
            source = wrapper / 'internal/cronet'
            source.mkdir(parents=True)
            (source / 'loader_windows.go').write_text(f'registerFunc(&engineCreate, "{core}")')
            (source / 'loader_windows_float.go').write_text('\n'.join(
                f'registerFunc(&function, "{symbol}")' for symbol in floats))
            for arch in ('amd64', 'arm64'):
                with self.subTest(arch=arch):
                    required = required_cronet_symbols(wrapper, 'windows', arch)
                    self.assertEqual(required, {core, *floats})
                    verify_required_exports(required, required)
                    for missing in floats:
                        with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, missing):
                            verify_required_exports(required, required - {missing})


if __name__ == '__main__':
    unittest.main()
