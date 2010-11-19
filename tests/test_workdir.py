# -*- coding: utf-8 -*-

# Copyright 2010 Mats Ekberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import with_statement
import sys, os, unittest, tempfile, shutil
from copy import copy

DATA1 = "tjosan"
DATA1_MD5 = "5558e0551622725a5fa380caffa94c5d"
DATA2 = "tjosan hejsan"
DATA2_MD5 = "923574a1a36aebc7e1f586b7d363005e"

TMPDIR=tempfile.gettempdir()

""" 
note: to execute a single test, do something like:
python tests/test_workdir.py TestWorkdir.testGetChangesMissingFile
"""

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workdir
from blobrepo import repository
from common import get_tree, my_relpath

def read_tree(path):
    """Returns a mapping {filename: content, ...} for the given directory
    tree"""
    assert os.path.exists(path)
    def visitor(out_map, dirname, names):
        encoding = sys.getfilesystemencoding()
        dirname = dirname.decode(encoding)
        for name in names:
            name = name.decode(encoding)
            fullpath = os.path.join(dirname, name)
            assert fullpath.startswith(path+"/")
            relpath = fullpath[len(path)+1:]
            if not os.path.isdir(fullpath):
                out_map[relpath] = open(fullpath).read()
    result = {}
    os.path.walk(path, visitor, result)
    return result

def write_tree(path, filemap):
    """Accepts a mapping {filename: content, ...} and writes it to the
    tree starting at the given """
    assert os.path.exists(path)
    for filename in filemap.keys():
        assert not os.path.exists(filename)
        assert not os.path.isabs(filename)
        fullpath = os.path.join(path, filename)
        dirpath = os.path.dirname(fullpath)
        try:
            os.makedirs(dirpath)
        except:
            pass
        with open(fullpath, "wb") as f:
            f.write(filemap[filename])

class WorkdirHelper:
    def mkdir(self, path):
        assert not os.path.isabs(path)
        dirpath = os.path.join(self.workdir, path)
        os.makedirs(dirpath)

    def addWorkdirFile(self, path, content):
        assert not os.path.isabs(path)
        filepath = os.path.join(self.workdir, path)
        with open(filepath, "w") as f:
            f.write(content)
    
    def rmWorkdirFile(self, path):
        assert not os.path.isabs(path)
        filepath = os.path.join(self.workdir, path)
        os.unlink(filepath)

    def createTmpName(self, suffix = ""):
        filename = tempfile.mktemp(prefix='testworkdir'+suffix+"_", dir=TMPDIR)
        self.remove_at_teardown.append(filename)
        return filename

    def assertContents(self, path, expected_contents):
        with open(path, "rb") as f:
            file_contents = f.read()
            self.assertEquals(file_contents, expected_contents)
        

class TestWorkdir(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName()
        self.repopath = self.createTmpName()
        repository.create_repository(self.repopath)
        os.mkdir(self.workdir)
        self.wd = workdir.Workdir(self.repopath, "TestSession", "", None, self.workdir)
        id = self.wd.checkin()
        assert id == 1

    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

    #
    # Actual tests start here
    #

    def testEmpty(self):
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((), (), (), (), ()))

    def testGetChangesUnversionedFile(self):
        # Test unversioned file
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((), ("tjosan.txt",), (), (), ()))

    def testGetChangesUnchangedFile(self):        
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, (("tjosan.txt",), (), (), (), ()))

    def testGetChangesUnchangedFileWithFunkyName(self):        
        name = u"Tjosan_räk smörgås.txt"
        self.addWorkdirFile(name, "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((name,), (), (), (), ()))

    def testGetChangesMissingFile(self):
        self.addWorkdirFile("tjosan.txt", "tjosanhejsan")
        self.wd.checkin()
        self.rmWorkdirFile("tjosan.txt")
        changes = self.wd.get_changes()
        self.assertEqual(changes, ((), (), (), ("tjosan.txt",), ()))

    def testGetChangesUnchangedFileSubdir(self):
        self.mkdir("subdir")
        self.addWorkdirFile("subdir/tjosan.txt", "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        self.assertEqual(changes, (("subdir/tjosan.txt",), (), (), (), ()))

    def testTwoNewIdenticalFiles(self):
        self.mkdir("subdir")
        self.addWorkdirFile("subdir/tjosan1.txt", "tjosanhejsan")
        self.addWorkdirFile("subdir/tjosan2.txt", "tjosanhejsan")
        self.wd.checkin()
        changes = self.wd.get_changes()
        # Order doesnt matter below really, so this is fragile
        self.assertEqual(changes, (tuple(["subdir/tjosan2.txt", "subdir/tjosan1.txt"]), (), (), (), ()))

    def testWriteAndReadTree(self):
        """ Really only test helper functions write_tree() and
        read_tree() themselves"""
        tree = {"tjosan.txt": "tjosan content",
                "subdir/nisse.txt": "nisse content"}
        testdir = self.createTmpName()
        os.mkdir(testdir)
        write_tree(testdir, tree)
        tree2 = read_tree(testdir)
        self.assertEqual(tree, tree2)

class TestPartialCheckin(unittest.TestCase, WorkdirHelper):
    def setUp(self):
        self.remove_at_teardown = []
        self.workdir = self.createTmpName("_wd")
        self.repopath = self.createTmpName("_repo")
        repository.create_repository(self.repopath)

    def createTestRepo(self):
        os.mkdir(self.workdir)
        wd = workdir.Workdir(self.repopath, "TestSession", "", None, self.workdir)
        self.addWorkdirFile("onlyintopdir.txt", "nothing")
        self.mkdir("mysubdir")
        self.addWorkdirFile("mysubdir/insubdir.txt", "nothing2")
        id = wd.checkin()
        assert id == 1
        shutil.rmtree(self.workdir, ignore_errors = True)

    def tearDown(self):
        for d in self.remove_at_teardown:
            shutil.rmtree(d, ignore_errors = True)

    def testPartialCheckout(self):
        self.createTestRepo()
        os.mkdir(self.workdir)
        wd = workdir.Workdir(self.repopath, "TestSession", "mysubdir", None, self.workdir)
        wd.checkout()
        tree = get_tree(wd.root, absolute_paths = False)
        #tree = wd.get_tree(absolute_paths = True)
        self.assertEquals(set(tree), set(["insubdir.txt", '.meta/info']))

if __name__ == '__main__':
    unittest.main()

