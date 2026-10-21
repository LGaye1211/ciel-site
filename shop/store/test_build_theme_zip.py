"""Tests for build_theme_zip.py. Run from shop/store:  python -m unittest -v"""

import contextlib
import io
import os
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_theme_zip as bt  # noqa: E402

THEME = {
    "layout/theme.liquid": b"<html>{{ content_for_header }}{{ content_for_layout }}</html>\r\n",
    "config/settings_schema.json": b"[]",
    "config/settings_data.json": (
        b'/*\n * auto-generated\n */\n'
        b'{"current": {"url": "https://example.com//x", "note": "a /* b */ c"}} // tail\n'
    ),
    "templates/index.json": b'{"sections": {}, "order": []}',
    "sections/header-group.json": b'{"sections": {}, "order": []}',
    "snippets/x.liquid": b"x",
    "assets/base.css": b"a{}",
    "locales/en.default.json": b"{}",
    "LICENSE.md": b"license text",
}

JUNK = {
    "README.md": b"readme",
    ".gitignore": b"x",
    ".theme-check.yml": b"x",
    ".github/workflows/ci.yml": b"x",
    "node_modules/pkg/index.js": b"x",
    ".git": b"gitdir: ../elsewhere",
    ".DS_Store": b"x",
    "assets/.DS_Store": b"x",
    "__MACOSX/._base.css": b"x",
    "assets/._base.css": b"x",
}


def write_tree(root, files):
    for name, data in files.items():
        path = os.path.join(root, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)


def write_zip_raw(path, files, prefix=""):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(prefix + name, data)


def zip_contents(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bt.main(list(args))
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.src = self.path("src")
        self.zip = self.path("download.zip")
        self.out = self.path("out", "shopify-theme.zip")
        os.makedirs(os.path.dirname(self.out))

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def build_ok(self, source, *extra):
        code, out, err = run(source, "-o", self.out, *extra)
        self.assertEqual(code, 0, out + err)
        return zip_contents(self.out)


class BuildFromFolder(Base):
    def test_keeps_theme_files_and_license_byte_for_byte(self):
        write_tree(self.src, {**THEME, **JUNK})
        self.assertEqual(self.build_ok(self.src), THEME)

    def test_no_license_flag(self):
        write_tree(self.src, THEME)
        expected = {k: v for k, v in THEME.items() if k != "LICENSE.md"}
        self.assertEqual(self.build_ok(self.src, "--no-license"), expected)

    def test_folder_that_wraps_the_theme(self):
        write_tree(self.src, {"wrapper/" + k: v for k, v in THEME.items()})
        self.assertEqual(self.build_ok(self.src), THEME)

    def test_blocks_folder_is_kept(self):
        write_tree(self.src, {**THEME, "blocks/b.liquid": b"b"})
        self.assertIn("blocks/b.liquid", self.build_ok(self.src))

    def test_summary_names_what_was_left_out(self):
        write_tree(self.src, {**THEME, **JUNK})
        code, out, _ = run(self.src, "-o", self.out)
        self.assertEqual(code, 0)
        self.assertIn("left out", out)
        self.assertIn("README.md", out)
        self.assertNotIn("node_modules", out)

    def test_default_output_name_is_shopify_theme_zip(self):
        write_tree(self.src, THEME)
        old = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, old)
        code, _, err = run(self.src)
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(self.path("shopify-theme.zip")))


class BuildFromGithubZip(Base):
    def test_wrapper_folder_is_stripped_and_junk_dropped(self):
        write_zip_raw(self.zip, {**THEME, **JUNK}, prefix="ciel-site-shopify-theme/")
        self.assertEqual(self.build_ok(self.zip), THEME)

    def test_directory_entries_are_ignored(self):
        with zipfile.ZipFile(self.zip, "w") as zf:
            zf.writestr("wrap/", b"")
            zf.writestr("wrap/layout/", b"")
            for name, data in THEME.items():
                zf.writestr("wrap/" + name, data)
        self.assertEqual(self.build_ok(self.zip), THEME)

    def test_backslash_paths_from_old_zip_tools_are_normalised(self):
        write_zip_raw(self.zip, {k.replace("/", "\\"): v for k, v in THEME.items()})
        self.assertEqual(self.build_ok(self.zip), THEME)

    def test_folder_and_zip_builds_are_identical(self):
        write_tree(self.src, THEME)
        write_zip_raw(self.zip, THEME, prefix="w/")
        self.build_ok(self.src)
        with open(self.out, "rb") as handle:
            from_folder = handle.read()
        self.build_ok(self.zip)
        with open(self.out, "rb") as handle:
            self.assertEqual(handle.read(), from_folder)


class Determinism(Base):
    def test_same_input_same_bytes(self):
        write_tree(self.src, THEME)
        second = self.path("out", "second.zip")
        self.assertEqual(run(self.src, "-o", self.out)[0], 0)
        self.assertEqual(run(self.src, "-o", second)[0], 0)
        with open(self.out, "rb") as a, open(second, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_independent_of_file_order_and_mtime(self):
        a, b = self.path("a"), self.path("b")
        write_tree(a, THEME)
        write_tree(b, dict(reversed(list(THEME.items()))))
        for here, _dirs, names in os.walk(b):
            for name in names:
                os.utime(os.path.join(here, name), (1_000_000_000, 1_000_000_000))
        out_a, out_b = self.path("out", "a.zip"), self.path("out", "b.zip")
        self.assertEqual(run(a, "-o", out_a)[0], 0)
        self.assertEqual(run(b, "-o", out_b)[0], 0)
        with open(out_a, "rb") as fa, open(out_b, "rb") as fb:
            self.assertEqual(fa.read(), fb.read())

    def test_entry_metadata_is_fixed_and_zip_is_sound(self):
        write_tree(self.src, THEME)
        self.build_ok(self.src)
        with zipfile.ZipFile(self.out) as zf:
            self.assertIsNone(zf.testzip())
            names = [i.filename for i in zf.infolist()]
            self.assertEqual(names, sorted(names))
            for info in zf.infolist():
                self.assertFalse(info.filename.endswith("/"))
                self.assertEqual(info.date_time, bt.FIXED_TIME)
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.external_attr, (stat.S_IFREG | 0o644) << 16)
                self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)

    def test_no_partial_file_left_behind(self):
        write_tree(self.src, THEME)
        self.build_ok(self.src)
        self.assertEqual(os.listdir(os.path.dirname(self.out)), ["shopify-theme.zip"])


class Validation(Base):
    def fail(self, files, *needles, source_is_zip=True):
        if source_is_zip:
            write_zip_raw(self.zip, files)
            source = self.zip
        else:
            write_tree(self.src, files)
            source = self.src
        code, out, err = run(source, "-o", self.out)
        self.assertEqual(code, 1, out + err)
        for needle in needles:
            self.assertIn(needle, out)
        self.assertFalse(os.path.exists(self.out))
        self.assertEqual(os.listdir(os.path.dirname(self.out)), [])

    def test_no_theme_in_source_points_at_the_theme_branch(self):
        self.fail({"README.md": b"x", "shop/store/x.md": b"x"}, "layout/theme.liquid not found", "shopify-theme branch")

    def test_two_themes_at_the_same_depth_are_ambiguous(self):
        self.fail({"a/layout/theme.liquid": b"x", "b/layout/theme.liquid": b"x"}, "more than one theme")

    def test_shallowest_theme_wins(self):
        write_zip_raw(self.zip, {**THEME, "backup/layout/theme.liquid": b"old"})
        self.assertEqual(self.build_ok(self.zip), THEME)

    def test_shallowest_wins_even_when_it_sorts_last(self):
        files = {"z/" + k: v for k, v in THEME.items()}
        files["a/b/layout/theme.liquid"] = b"deeper copy that sorts first"
        write_zip_raw(self.zip, files)
        self.assertEqual(self.build_ok(self.zip), THEME)

    def test_missing_pieces_are_named(self):
        cases = {
            "snippets/x.liquid": "missing or empty folder: snippets/",
            "config/settings_schema.json": "missing file: config/settings_schema.json",
            "templates/index.json": "missing file: templates/index.json",
            "locales/en.default.json": "missing default locale",
        }
        for removed, needle in cases.items():
            with self.subTest(removed=removed):
                files = {k: v for k, v in THEME.items() if k != removed}
                self.fail(files, needle)

    def test_layout_without_content_for_header(self):
        files = {**THEME, "layout/theme.liquid": b"<html>{{ content_for_layout }}</html>"}
        self.fail(files, "layout/theme.liquid is missing content_for_header")

    def test_invalid_json_names_the_file(self):
        files = {**THEME, "templates/index.json": b'{"a": }'}
        self.fail(files, "invalid JSON: templates/index.json")

    def test_invalid_json_in_a_folder_source(self):
        files = {**THEME, "sections/header-group.json": b"{"}
        self.fail(files, "invalid JSON: sections/header-group.json", source_is_zip=False)

    def test_utf8_bom_json_is_accepted(self):
        write_zip_raw(self.zip, {**THEME, "locales/en.default.json": b"\xef\xbb\xbf{}"})
        self.assertIn("locales/en.default.json", self.build_ok(self.zip))


class StripComments(unittest.TestCase):
    def test_comments_removed_and_strings_kept(self):
        text = '/* head */ {"u": "https://x.y/z", "c": "/* not */", "d": "// no"} // tail'
        self.assertEqual(
            bt.json.loads(bt.strip_json_comments(text)),
            {"u": "https://x.y/z", "c": "/* not */", "d": "// no"},
        )

    def test_escaped_quote_does_not_end_the_string(self):
        text = '{"a": "say \\"//\\" now"}'
        self.assertEqual(bt.strip_json_comments(text), text)

    def test_block_comment_keeps_its_newlines(self):
        stripped = bt.strip_json_comments("/*\n\n\n*/{\n}")
        self.assertEqual(stripped.count("\n"), 4)

    def test_line_comment_at_end_without_newline(self):
        self.assertEqual(bt.strip_json_comments("{} // x"), "{} ")

    def test_unterminated_block_comment_raises(self):
        with self.assertRaises(ValueError):
            bt.strip_json_comments("{} /* open")


class Safety(Base):
    def test_zip_slip_names_are_rejected(self):
        bad = ["../evil.txt", "/abs/evil.txt", "a/../../b.txt", "C:/evil.txt", "..\\evil.txt", "x/../y.txt"]
        for name in bad:
            with self.subTest(name=name):
                write_zip_raw(self.zip, {**THEME, name: b"x"})
                code, _, err = run(self.zip, "-o", self.out)
                self.assertEqual(code, 2)
                self.assertIn("unsafe path", err)
                self.assertFalse(os.path.exists(self.out))

    def test_nul_byte_in_name_is_rejected(self):
        with self.assertRaises(bt.InputError):
            bt.normalise("a\x00b")

    def test_symlink_entry_in_zip_is_rejected(self):
        with zipfile.ZipFile(self.zip, "w") as zf:
            for name, data in THEME.items():
                zf.writestr(name, data)
            link = zipfile.ZipInfo("assets/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(link, "/etc/passwd")
        code, _, err = run(self.zip, "-o", self.out)
        self.assertEqual(code, 2)
        self.assertIn("symlink", err)

    def test_symlink_inside_an_excluded_folder_is_ignored(self):
        with zipfile.ZipFile(self.zip, "w") as zf:
            for name, data in THEME.items():
                zf.writestr(name, data)
            link = zipfile.ZipInfo("node_modules/.bin/tool")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(link, "../tool.js")
        self.assertEqual(self.build_ok(self.zip), THEME)

    def test_symlink_in_a_folder_is_rejected(self):
        write_tree(self.src, THEME)
        try:
            os.symlink("/etc/hostname", os.path.join(self.src, "assets", "link"))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlinks unavailable here")
        code, _, err = run(self.src, "-o", self.out)
        self.assertEqual(code, 2)
        self.assertIn("symlink", err)

    def test_duplicate_entries_are_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(self.zip, "w") as zf:
                for name, data in THEME.items():
                    zf.writestr(name, data)
                zf.writestr("layout/theme.liquid", b"second")
                zf.writestr("assets//base.css", b"dup after cleanup")
        code, _, err = run(self.zip, "-o", self.out)
        self.assertEqual(code, 2)
        self.assertIn("duplicate entry", err)

    def test_file_count_cap(self):
        write_tree(self.src, THEME)
        write_zip_raw(self.zip, THEME)
        with mock.patch.object(bt, "MAX_FILES", 3):
            for source in (self.src, self.zip):
                with self.subTest(source=source):
                    code, _, err = run(source, "-o", self.out)
                    self.assertEqual(code, 2)
                    self.assertIn("too many or too large", err)

    def test_total_size_cap(self):
        write_tree(self.src, THEME)
        write_zip_raw(self.zip, THEME)
        with mock.patch.object(bt, "MAX_TOTAL_BYTES", 10):
            for source in (self.src, self.zip):
                with self.subTest(source=source):
                    code, _, err = run(source, "-o", self.out)
                    self.assertEqual(code, 2)
                    self.assertIn("too many or too large", err)

    def test_output_inside_the_theme_folder_is_rejected(self):
        write_tree(self.src, THEME)
        code, _, err = run(self.src, "-o", os.path.join(self.src, "assets", "x.zip"))
        self.assertEqual(code, 2)
        self.assertIn("inside the theme folder", err)

    def test_output_equal_to_the_input_zip_is_rejected(self):
        write_zip_raw(self.zip, THEME)
        before = zip_contents(self.zip)
        code, _, err = run(self.zip, "-o", self.zip)
        self.assertEqual(code, 2)
        self.assertIn("same as the input", err)
        self.assertEqual(zip_contents(self.zip), before)

    def test_missing_output_folder_is_rejected(self):
        write_tree(self.src, THEME)
        code, _, err = run(self.src, "-o", self.path("nope", "x.zip"))
        self.assertEqual(code, 2)
        self.assertIn("output folder does not exist", err)

    def test_missing_source_and_non_zip_source(self):
        code, _, err = run(self.path("missing"), "-o", self.out)
        self.assertEqual((code, "no such file" in err), (2, True))
        text = self.path("note.txt")
        with open(text, "w") as handle:
            handle.write("not a zip")
        code, _, err = run(text, "-o", self.out)
        self.assertEqual((code, "not a zip" in err), (2, True))


if __name__ == "__main__":
    unittest.main()
