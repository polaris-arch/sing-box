import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

SCRIPT = pathlib.Path(__file__).with_name('polaris_desktop_source_candidate.py')


class SourceAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.stage = self.root / 'stage'
        self.stage.mkdir()
        closure = self.root / 'evidence/cronet-license-closure'
        closure.mkdir(parents=True)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.go = self.root / 'go.zip'
        with zipfile.ZipFile(self.go, 'w') as z:
            z.writestr('toolchain/src/a.go', b'package a\n')
            z.writestr('toolchain/LICENSE', b'Go license\n')
        notice = self.stage / 'DESKTOP-SOURCE-NOTICE-SUPERSET.txt'
        notice.write_bytes(b'NOTICE\r\n')
        source = closure / 'source.tar'
        source.write_bytes(b'fixed source')
        recipe = self.stage / 'build-recipes/script.py'
        recipe.parent.mkdir()
        recipe.write_bytes(b'print("recipe")\n')
        module = self.cache / 'example/@v/v1.zip'
        module.parent.mkdir(parents=True)
        module.write_bytes(b'fixed module')
        self.index = {
            'publicationEligible': False, 'packageNoticeInputsAdoptedByProducer': False,
            'platforms': [{'nativeAccepted': True}] * 3,
            'sourceCommit': 'frozen-source', 'sourceArchiveInputs': [dict(filename=source.name, **self.record(source))],
            'noticeBundle': self.record(notice),
            'noticeRecords': [dict(byteOffset=0, **self.record(notice))],
            'buildRecipeInputs': [dict(path='build-recipes/script.py', **self.record(recipe))],
            'sourceAssemblyInputs': [],
            'modules': [{'sourceBundleMember': 'modules/example/@v/v1.zip',
                         'zipBytes': module.stat().st_size, 'zipSha256': self.sha(module)}],
            'localGoToolchainInput': {'zipSha256': self.sha(self.go)}
        }
        self.write_index()
        self.command = [sys.executable, str(SCRIPT), '--evidence-root', str(self.root / 'evidence'),
                        '--stage-dir', str(self.stage), '--module-cache', str(self.cache),
                        '--go-toolchain-zip', str(self.go)]

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def record(self, path):
        return {'bytes': path.stat().st_size, 'sha256': self.sha(path)}

    def write_index(self):
        (self.stage / 'DESKTOP-SOURCE-NOTICE-INDEX-controlled.json').write_text(json.dumps(self.index))

    def run_helper(self, *args, optimized=False):
        command = list(self.command)
        if optimized:
            command.insert(1, '-O')
        return subprocess.run(command + list(args), capture_output=True, text=True)

    def reject(self, message, optimized=False):
        result = self.run_helper('--validate-only', optimized=optimized)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)

    def test_valid_inputs_and_actual_archive(self):
        self.assertEqual(self.run_helper('--validate-only').returncode, 0)
        output = self.root / 'output'
        result = self.run_helper('--output-dir', str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        bundle = output / receipt['filename']
        self.assertEqual(self.sha(bundle), receipt['sha256'])
        with tarfile.open(bundle) as archive:
            self.assertEqual(archive.extractfile('notices/DESKTOP-SOURCE-NOTICE-SUPERSET.txt').read(), b'NOTICE\r\n')
            self.assertEqual(archive.extractfile('modules/example/@v/v1.zip').read(), b'fixed module')
        self.assertEqual((self.stage / 'DESKTOP-SOURCE-NOTICE-SUPERSET.txt').read_bytes(), b'NOTICE\r\n')
        self.assertNotEqual(self.run_helper('--output-dir', str(output)).returncode, 0)
        self.assertEqual(self.sha(bundle), receipt['sha256'])

    def run_with_post_preflight_rewrite(self, target, replacement, expected_error):
        spec = importlib.util.spec_from_file_location('packager_under_test', SCRIPT)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        original_hash = helper.file_hash
        original_bytes = target.read_bytes()
        self.assertEqual(len(original_bytes), len(replacement))
        rewritten = False

        def injected_hash(path):
            nonlocal rewritten
            result = original_hash(path)
            if pathlib.Path(path) == self.go and not rewritten:
                # Go input is checked after source inputs, immediately before assembly.
                target.write_bytes(replacement)
                rewritten = True
            return result

        output = self.root / 'post-preflight-output'
        with mock.patch.object(helper, 'file_hash', injected_hash), mock.patch.object(
                sys, 'argv', self.command[1:] + ['--output-dir', str(output)]):
            with self.assertRaisesRegex(ValueError, expected_error):
                helper.main()
        self.assertTrue(rewritten)
        self.assertFalse((output / 'bounded-source-package-receipt-v3.json').exists())
        self.assertFalse((output / 'polaris-box-a01-desktop-source-candidate-three-platforms-v3.tar.gz').exists())
        target.write_bytes(original_bytes)

    def test_same_length_rewrite_after_preflight_rejects_unapproved_member(self):
        self.run_with_post_preflight_rewrite(
            self.cache / 'example/@v/v1.zip', b'wrong module',
            'packaged member differs from frozen expected SHA256')

    def test_toolchain_rewrite_after_preflight_cannot_change_derived_source(self):
        self.run_with_post_preflight_rewrite(
            self.go, b'x' * self.go.stat().st_size,
            'verified Go toolchain snapshot SHA256 mismatch')

    def test_notice_corruption_rejected_even_with_python_optimization(self):
        (self.stage / 'DESKTOP-SOURCE-NOTICE-SUPERSET.txt').write_bytes(b'NOTICE!\n')
        self.reject('notice bundle SHA256 mismatch', optimized=True)

    def test_slice_mismatch(self):
        self.index['noticeRecords'][0]['byteOffset'] = 1
        self.write_index()
        self.reject('notice slice SHA256 mismatch')

    def test_module_digest_mismatch(self):
        (self.cache / 'example/@v/v1.zip').write_bytes(b'badxx module')
        self.reject('input SHA256 mismatch')

    def test_archive_digest_mismatch(self):
        (self.root / 'evidence/cronet-license-closure/source.tar').write_bytes(b'wrong source')
        self.reject('input SHA256 mismatch')

    def test_recipe_digest_mismatch(self):
        self.index['buildRecipeInputs'][0]['sha256'] = '0' * 64
        self.write_index()
        self.reject('input SHA256 mismatch')

    def test_traversal_and_absolute_members(self):
        for name in ['../escape', '/absolute', 'C:/escape', 'bad\\name', '', 'x/../escape']:
            with self.subTest(name=name):
                self.index['buildRecipeInputs'][0]['path'] = name
                self.write_index()
                self.reject('unsafe source package member')

    def test_symlink_escape(self):
        outside = self.root / 'outside.py'
        outside.write_bytes(b'print("recipe")\n')
        recipe = self.stage / 'build-recipes/script.py'
        recipe.unlink()
        recipe.symlink_to(outside)
        self.reject('input escapes declared root')

    def test_duplicate_archive_member(self):
        self.index['sourceAssemblyInputs'] = self.index['buildRecipeInputs'][:]
        self.write_index()
        self.reject('duplicate source input member')

    def test_toolchain_digest_mismatch(self):
        self.index['localGoToolchainInput']['zipSha256'] = '0' * 64
        self.write_index()
        self.reject('Go toolchain source ZIP SHA256 mismatch')

    def test_relabelled_six_platform_scope_rejected(self):
        self.index['platforms'] *= 2
        self.write_index()
        self.reject('only covers three original platforms')


if __name__ == '__main__':
    unittest.main()
