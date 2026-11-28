import unittest
from unittest.mock import patch
import rose_fast_cli as fast
import rose_catalog as cat


class FastCLI(unittest.TestCase):
    def test_fallback_for_global_flags_and_write_operations(self):
        for args in ([], ["--db", "x", "find", "video"], ["start"], ["render"], ["catalog-build"], ["maintain"], ["--help"]):
            self.assertIsNone(fast.dispatch(args))

    def test_only_selected_module_loaded(self):
        class Module:
            @staticmethod
            def register(sub):
                p=sub.add_parser("find")
                p.add_argument("query")
                p.set_defaults(ext_func=lambda args: 7 if args.query=="video" else 1)
        with patch.object(fast.importlib,"import_module",return_value=Module) as imp:
            self.assertEqual(fast.dispatch(["find","video"]),7)
            imp.assert_called_once_with("rose_catalog")

    def test_cache_uses_content_and_preserves_weights(self):
        a,b=cat._search_words("فيديو","Video","motion video",("video",))
        self.assertIn("video",a)
        self.assertIn("motion",b)
        c,_=cat._search_words("فيديو","Audio","motion video",("audio",))
        self.assertIn("audio",c)
        self.assertNotIn("video",c)

    def test_search_matches_original_scoring(self):
        data=cat.load()
        for query in ("video motion","دعاء فيديو","audio export","مراجعة حساب"):
            terms=set(t for t in cat.tokens(query) if t not in cat._STOP)
            for key, extra in data.get("synonyms",{}).items():
                kt=cat.tokens(key)
                if kt and kt[0] in terms:
                    for value in extra: terms.update(cat.tokens(value))
            expected=[]
            for op,e in data["entries"].items():
                keys=set(e.get("keywords",[]))|set(cat.tokens(e.get("name_ar","")))|set(cat.tokens(e.get("name_en","")))
                words=set(cat.tokens(e.get("summary","")))
                score=sum(3 if t in keys else 1 if t in words else 0 for t in terms)
                if score: expected.append((-score,op,sorted(terms & (keys|words))))
            expected.sort()
            actual=[(-v["score"],v["id"],v["matched"]) for v in cat.find(query,8)]
            self.assertEqual(actual,expected[:8])
