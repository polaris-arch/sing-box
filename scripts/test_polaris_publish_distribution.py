import contextlib
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import polaris_publish_distribution as publish
import polaris_native_distribution as pack

class PublicationTests(unittest.TestCase):
    def test_actual_local_manifest_and_all_ten_assets(self):
        repo=Path(__file__).resolve().parents[1]
        path=repo/'release/native-publication/prepared-upload-assets.json'
        # Test the actual verified local candidate folder supplied by author delivery.
        import os
        directory=os.environ.get('POLARIS_PREPARED_ASSETS')
        if not directory:self.skipTest('actual offline assets folder required for integration verification')
        actual=Path(directory)/'UPLOAD-ASSETS.json'
        self.assertEqual(actual.read_bytes(),path.read_bytes())
        publish.validate_manifest(actual,hashlib.sha256(actual.read_bytes()).hexdigest())
    def test_remote_extra_missing_wrong_size_digest_rejected(self):
        manifest={'assets':[{'name':str(i),'bytes':1,'sha256':'a'*64} for i in range(10)]}
        assets=[{'name':str(i),'size':1,'digest':'sha256:'+'a'*64} for i in range(10)]
        publish.validate_remote_assets({'assets':assets},manifest)
        for values in [assets[:-1],assets+[assets[0]], [dict(x,size=2) for x in assets], [dict(x,digest=None) for x in assets]]:
            with self.assertRaises(ValueError):publish.validate_remote_assets({'assets':values},manifest)
    def test_unannotated_or_wrong_tag_target_rejected(self):
        for refs in ['abc refs/tags/'+publish.TAG, 'abc refs/tags/'+publish.TAG+'\nwrong refs/tags/'+publish.TAG+'^{}']:
            with patch.object(publish,'command',return_value=refs):
                with self.assertRaises(ValueError):publish.validate_tag(Path('/tmp/source'))
    def test_unauthenticated_public_readback_hash_size(self):
        data=b'actual asset';digest=hashlib.sha256(data).hexdigest()
        assets=[{'name':str(i),'bytes':len(data),'sha256':digest} for i in range(10)]
        release={'assets':[{'name':str(i),'size':len(data),'digest':'sha256:'+digest} for i in range(10)]}
        class Response:
            def __enter__(self):self.done=False;return self
            def __exit__(self,*args):pass
            def read(self,count):
                if self.done:return b''
                self.done=True;return data
        requests=[]
        def open_request(request,timeout):requests.append(request);return Response()
        with patch.object(publish.urllib.request,'urlopen',side_effect=open_request):
            records=publish.public_readback(release,{'assets':assets})
        self.assertEqual(len(records),10)
        for request in requests:
            self.assertFalse(request.has_header('Authorization'))
            self.assertTrue(request.full_url.startswith('https://github.com/polaris-arch/polaris-box/releases/download/'+publish.TAG+'/'))
        with patch.object(publish.urllib.request,'urlopen',side_effect=open_request):
            assets[0]['sha256']='0'*64;release['assets'][0]['digest']='sha256:'+'0'*64
            with self.assertRaises(ValueError):publish.public_readback(release,{'assets':assets})
    def test_manifest_drift_blocks_before_any_remote_action(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'UPLOAD-ASSETS.json';path.write_text('{}')
            with self.assertRaises(ValueError):publish.validate_manifest(path,'0'*64)

if __name__=='__main__':unittest.main()
