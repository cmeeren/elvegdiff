# Run from dir with elvegdiff.py like this:
#    python tests/test_elvegdiff.py

import subprocess
p = subprocess.Popen(['python', 'elvegdiff.py', 'tests/test_old.osm', 'tests/test_new.osm', 'tests/test_out_'])
p.wait()

with open(r'tests/test_changed_correct.osm') as f_changed_correct,\
        open(r'tests/test_out_changed.osm') as f_changed_out,\
        open(r'tests/test_deleted_correct.osm') as f_deleted_correct,\
        open(r'tests/test_out_deleted.osm') as f_deleted_out:
    assert f_changed_correct.read() == f_changed_out.read()
    assert f_deleted_correct.read() == f_deleted_out.read()
