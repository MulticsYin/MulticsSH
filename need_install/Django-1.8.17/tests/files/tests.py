# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import gzip
import os
import tempfile
import unittest
import zlib
from io import BytesIO, StringIO

from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.move import file_move_safe
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.utils import six
from django.utils._os import upath

try:
    from PIL import Image
except ImportError:
    Image = None
else:
    from django.core.files import images


class FileTests(unittest.TestCase):
    def test_unicode_uploadedfile_name(self):
        uf = UploadedFile(name='¿Cómo?', content_type='text')
        self.assertIs(type(repr(uf)), str)

    def test_unicode_file_name(self):
        f = File(None, 'djángö')
        self.assertIs(type(repr(f)), str)

    def test_context_manager(self):
        orig_file = tempfile.TemporaryFile()
        base_file = File(orig_file)
        with base_file as f:
            self.assertIs(base_file, f)
            self.assertFalse(f.closed)
        self.assertTrue(f.closed)
        self.assertTrue(orig_file.closed)

    def test_namedtemporaryfile_closes(self):
        """
        The symbol django.core.files.NamedTemporaryFile is assigned as
        a different class on different operating systems. In
        any case, the result should minimally mock some of the API of
        tempfile.NamedTemporaryFile from the Python standard library.
        """
        tempfile = NamedTemporaryFile()
        self.assertTrue(hasattr(tempfile, "closed"))
        self.assertFalse(tempfile.closed)

        tempfile.close()
        self.assertTrue(tempfile.closed)

    def test_file_mode(self):
        # Should not set mode to None if it is not present.
        # See #14681, stdlib gzip module crashes if mode is set to None
        file = SimpleUploadedFile("mode_test.txt", b"content")
        self.assertFalse(hasattr(file, 'mode'))
        gzip.GzipFile(fileobj=file)

    def test_file_iteration(self):
        """
        File objects should yield lines when iterated over.
        Refs #22107.
        """
        file = File(BytesIO(b'one\ntwo\nthree'))
        self.assertEqual(list(file), [b'one\n', b'two\n', b'three'])

    def test_file_iteration_windows_newlines(self):
        """
        #8149 - File objects with \r\n line endings should yield lines
        when iterated over.
        """
        f = File(BytesIO(b'one\r\ntwo\r\nthree'))
        self.assertEqual(list(f), [b'one\r\n', b'two\r\n', b'three'])

    def test_file_iteration_mac_newlines(self):
        """
        #8149 - File objects with \r line endings should yield lines
        when iterated over.
        """
        f = File(BytesIO(b'one\rtwo\rthree'))
        self.assertEqual(list(f), [b'one\r', b'two\r', b'three'])

    def test_file_iteration_mixed_newlines(self):
        f = File(BytesIO(b'one\rtwo\nthree\r\nfour'))
        self.assertEqual(list(f), [b'one\r', b'two\n', b'three\r\n', b'four'])

    def test_file_iteration_with_unix_newline_at_chunk_boundary(self):
        f = File(BytesIO(b'one\ntwo\nthree'))
        # Set chunk size to create a boundary after \n:
        # b'one\n...
        #        ^
        f.DEFAULT_CHUNK_SIZE = 4
        self.assertEqual(list(f), [b'one\n', b'two\n', b'three'])

    def test_file_iteration_with_windows_newline_at_chunk_boundary(self):
        f = File(BytesIO(b'one\r\ntwo\r\nthree'))
        # Set chunk size to create a boundary between \r and \n:
        # b'one\r\n...
        #        ^
        f.DEFAULT_CHUNK_SIZE = 4
        self.assertEqual(list(f), [b'one\r\n', b'two\r\n', b'three'])

    def test_file_iteration_with_mac_newline_at_chunk_boundary(self):
        f = File(BytesIO(b'one\rtwo\rthree'))
        # Set chunk size to create a boundary after \r:
        # b'one\r...
        #        ^
        f.DEFAULT_CHUNK_SIZE = 4
        self.assertEqual(list(f), [b'one\r', b'two\r', b'three'])

    def test_file_iteration_with_text(self):
        f = File(StringIO('one\ntwo\nthree'))
        self.assertEqual(list(f), ['one\n', 'two\n', 'three'])


class NoNameFileTestCase(unittest.TestCase):
    """
    Other examples of unnamed files may be tempfile.SpooledTemporaryFile or
    urllib.urlopen()
    """
    def test_noname_file_default_name(self):
        self.assertEqual(File(BytesIO(b'A file with no name')).name, None)

    def test_noname_file_get_size(self):
        self.assertEqual(File(BytesIO(b'A file with no name')).size, 19)


class ContentFileTestCase(unittest.TestCase):
    def test_content_file_default_name(self):
        self.assertEqual(ContentFile(b"content").name, None)

    def test_content_file_custom_name(self):
        """
        Test that the constructor of ContentFile accepts 'name' (#16590).
        """
        name = "I can have a name too!"
        self.assertEqual(ContentFile(b"content", name=name).name, name)

    def test_content_file_input_type(self):
        """
        Test that ContentFile can accept both bytes and unicode and that the
        retrieved content is of the same type.
        """
        self.assertIsInstance(ContentFile(b"content").read(), bytes)
        if six.PY3:
            self.assertIsInstance(ContentFile("español").read(), six.text_type)
        else:
            self.assertIsInstance(ContentFile("español").read(), bytes)


class DimensionClosingBug(unittest.TestCase):
    """
    Test that get_image_dimensions() properly closes files (#8817)
    """
    @unittest.skipUnless(Image, "Pillow not installed")
    def test_not_closing_of_files(self):
        """
        Open files passed into get_image_dimensions() should stay opened.
        """
        empty_io = BytesIO()
        try:
            images.get_image_dimensions(empty_io)
        finally:
            self.assertTrue(not empty_io.closed)

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_closing_of_filenames(self):
        """
        get_image_dimensions() called with a filename should closed the file.
        """
        # We need to inject a modified open() builtin into the images module
        # that checks if the file was closed properly if the function is
        # called with a filename instead of an file object.
        # get_image_dimensions will call our catching_open instead of the
        # regular builtin one.

        class FileWrapper(object):
            _closed = []

            def __init__(self, f):
                self.f = f

            def __getattr__(self, name):
                return getattr(self.f, name)

            def close(self):
                self._closed.append(True)
                self.f.close()

        def catching_open(*args):
            return FileWrapper(open(*args))

        images.open = catching_open
        try:
            images.get_image_dimensions(os.path.join(os.path.dirname(upath(__file__)), "test1.png"))
        finally:
            del images.open
        self.assertTrue(FileWrapper._closed)


class InconsistentGetImageDimensionsBug(unittest.TestCase):
    """
    Test that get_image_dimensions() works properly after various calls
    using a file handler (#11158)
    """
    @unittest.skipUnless(Image, "Pillow not installed")
    def test_multiple_calls(self):
        """
        Multiple calls of get_image_dimensions() should return the same size.
        """
        img_path = os.path.join(os.path.dirname(upath(__file__)), "test.png")
        with open(img_path, 'rb') as fh:
            image = images.ImageFile(fh)
            image_pil = Image.open(fh)
            size_1 = images.get_image_dimensions(image)
            size_2 = images.get_image_dimensions(image)
        self.assertEqual(image_pil.size, size_1)
        self.assertEqual(size_1, size_2)

    @unittest.skipUnless(Image, "Pillow not installed")
    def test_bug_19457(self):
        """
        Regression test for #19457
        get_image_dimensions fails on some pngs, while Image.size is working good on them
        """
        img_path = os.path.join(os.path.dirname(upath(__file__)), "magic.png")
        try:
            size = images.get_image_dimensions(img_path)
        except zlib.error:
            self.fail("Exception raised from get_image_dimensions().")
        with open(img_path, 'rb') as fh:
            self.assertEqual(size, Image.open(fh).size)


class FileMoveSafeTests(unittest.TestCase):
    def test_file_move_overwrite(self):
        handle_a, self.file_a = tempfile.mkstemp()
        handle_b, self.file_b = tempfile.mkstemp()

        # file_move_safe should raise an IOError exception if destination file exists and allow_overwrite is False
        self.assertRaises(IOError, lambda: file_move_safe(self.file_a, self.file_b, allow_overwrite=False))

        # should allow it and continue on if allow_overwrite is True
        self.assertIsNone(file_move_safe(self.file_a, self.file_b, allow_overwrite=True))

        os.close(handle_a)
        os.close(handle_b)


class SpooledTempTests(unittest.TestCase):
    def test_in_memory_spooled_temp(self):
        with tempfile.SpooledTemporaryFile() as temp:
            temp.write(b"foo bar baz quux\n")
            django_file = File(temp, name="something.txt")
            self.assertEqual(django_file.size, 17)

    def test_written_spooled_temp(self):
        with tempfile.SpooledTemporaryFile(max_size=4) as temp:
            temp.write(b"foo bar baz quux\n")
            django_file = File(temp, name="something.txt")
            self.assertEqual(django_file.size, 17)
