from traceforge.endpoints import candidate_changed_lines


def test_candidate_changed_lines_tracks_only_added_side() -> None:
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,3 +10,4 @@
 context
-old
+new
+added
 context
"""
    assert candidate_changed_lines(diff) == {"app.py": {11, 12}}
