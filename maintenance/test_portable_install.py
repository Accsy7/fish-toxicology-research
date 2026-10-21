"""Installation and portability regressions using synthetic, read-only data fixtures."""
from pathlib import Path
from contextlib import closing
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'toolkit'), str(ROOT/'toolkit/tools')]
import install_bundle
from bundle_runtime import inspect
from research import doctor


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), 'utf-8')


class PortableInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root/'study'
        self.data = self.root/'data'
        self.revision = self.data/'revisions/0.4.2-local.1'
        self.revision.mkdir(parents=True)
        self.fish = self.data/'research.sqlite3'
        with closing(sqlite3.connect(self.fish)) as c:
            c.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT)')
            c.execute("INSERT INTO metadata VALUES('database_version','fixture-0.3.0')")
            c.commit()
        for path in [self.data/'molecular_support.sqlite3', self.revision/'observations.sqlite3']:
            with closing(sqlite3.connect(path)) as c:
                c.execute('CREATE TABLE fixture(value TEXT)')
                c.commit()
        dump(self.data/'policy/support_policy.json', {'version':'fixture'})
        self.catalog = self.revision/'catalog.json'
        dump(self.catalog, {'version':'0.4.2-local.1','paths': {
            'fish_database':'../../research.sqlite3', 'observations':'observations.sqlite3',
            'molecular_support':'../../molecular_support.sqlite3','policy':'../../policy/support_policy.json'}})

    def tearDown(self):
        self.temp.cleanup()

    def install(self, **kwargs):
        return install_bundle.install(self.project, **kwargs)

    def config(self):
        return json.loads((self.project/'.fish-toxicology/workspace.json').read_text('utf-8'))

    def test_unbound_install_reports_actual_state(self):
        result = self.install(client='both')
        self.assertEqual(result['errors'], [])
        self.assertEqual(self.install(client='both')['status'], 'already_installed')
        status = doctor(self.project)
        self.assertFalse(status['ready_for_local_queries'])
        self.assertTrue(status['ready_for_public_source_research'])
        self.assertEqual(status['database_status'], 'not_connected')

    def test_relative_catalog_binding_does_not_modify_data(self):
        files = [self.fish, self.catalog, self.revision/'observations.sqlite3']
        before = {path:path.read_bytes() for path in files}
        self.install(catalog=self.catalog)
        data = self.config()['database']
        self.assertEqual((self.project/data['catalog']).resolve(), self.catalog)
        self.assertEqual((self.project/data['file']).resolve(), self.fish)
        self.assertEqual(data['version'], 'fixture-0.3.0')
        self.assertEqual(data['catalog_version'], '0.4.2-local.1')
        self.assertFalse(Path(data['catalog']).is_absolute())
        self.assertTrue(all(path.read_bytes()==value for path,value in before.items()))

    def test_move_data_root_before_binding(self):
        moved = self.root/'another-data-root'
        self.assertTrue(self.data.resolve().is_relative_to(self.root.resolve()))
        self.assertTrue(moved.resolve().is_relative_to(self.root.resolve()))
        shutil.move(str(self.data), moved)
        catalog = moved/'revisions/0.4.2-local.1/catalog.json'
        self.install(catalog=catalog)
        self.assertEqual((self.project/self.config()['database']['file']).resolve(), moved/'research.sqlite3')

    def test_missing_revision_is_rejected_before_writes(self):
        (self.revision/'observations.sqlite3').unlink()
        with self.assertRaisesRegex(ValueError, 'observations'):
            self.install(catalog=self.catalog)
        self.assertFalse((self.project/'.fish-toxicology').exists())

    def test_mutually_exclusive_binding_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '只能选择一个'):
            self.install(database=self.fish, catalog=self.catalog)
        self.assertFalse((self.project/'.fish-toxicology').exists())

    def test_update_retains_research_frontend_and_database(self):
        self.install(catalog=self.catalog)
        note = self.project/'research/personal.txt'
        note.parent.mkdir(parents=True)
        note.write_text('keep original work', 'utf-8')
        config = self.config()
        config['custom_setting'] = {'keep':True}
        config['database']['frontend_version'] = '1.13.1-local.1'
        config['database']['browser'] = 'independent-ui/index.html'
        dump(self.project/'.fish-toxicology/workspace.json', config)
        result = self.install(update=True)
        self.assertEqual(result['status'], 'updated_tools')
        self.assertEqual(self.config()['database'], config['database'])
        self.assertEqual(self.config()['custom_setting'], config['custom_setting'])
        self.assertEqual(note.read_text('utf-8'), 'keep original work')
        self.assertFalse((self.project/'.fish-toxicology/tools/database_frontend').exists())

    def test_modified_tools_are_not_overwritten(self):
        self.install()
        path = self.project/'.fish-toxicology/tools/research.py'
        path.write_text('# user changes', 'utf-8')
        with self.assertRaisesRegex(ValueError, '修改'):
            self.install(update=True)
        self.assertEqual(path.read_text('utf-8'), '# user changes')

    def test_failed_post_install_check_rolls_back(self):
        self.install()
        directory = self.project/'.fish-toxicology'
        before = {path:path.read_bytes() for path in directory.rglob('*') if path.is_file()}
        original = install_bundle.inspect
        def injected(home, *args, **kwargs):
            result = original(home, *args, **kwargs)
            if Path(home).name == '.fish-toxicology':
                result['errors'] = ['injected failure']
            return result
        with patch.object(install_bundle, 'inspect', side_effect=injected):
            with self.assertRaisesRegex(ValueError, 'injected failure'):
                self.install(update=True)
        self.assertTrue(all(path.read_bytes()==value for path,value in before.items()))

    def test_discovery_and_manifest_match(self):
        self.install(client='both')
        result = inspect(self.project/'.fish-toxicology')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['modified_files'], [])
        for client in ['.agents', '.claude']:
            self.assertEqual((self.project/client/'skills/fish-toxicology-research/SKILL.md').read_bytes(),
                             (ROOT/'toolkit/skill/SKILL.md').read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
