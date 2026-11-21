"""Protect Arabic UTF-8 JSON against legacy CP1252 console encoding."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from rose import main

class UTF8ConsoleTest(unittest.TestCase):
 def test_utf8_stdout_from_cp1252_stream(self):
  with tempfile.TemporaryDirectory() as d:
   buffer=io.BytesIO()
   fake=io.TextIOWrapper(buffer,encoding='cp1252',write_through=True)
   original=sys.stdout
   try:
    sys.stdout=fake
    main(['--db',str(Path(d)/'m.sqlite3'),'capability-plan','عايز فيديو عربي'])
    fake.flush()
   finally:
    sys.stdout=original
   data=json.loads(buffer.getvalue().decode('utf-8'))
   self.assertEqual(data['task'],'عايز فيديو عربي')
   self.assertEqual(data['status'],'planned_not_executed')

if __name__=='__main__':unittest.main()
