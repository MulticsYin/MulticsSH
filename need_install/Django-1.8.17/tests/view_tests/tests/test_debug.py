# -*- coding: utf-8 -*-
# This coding header is significant for tests, as the debug view is parsing
# files to search for such a header to decode the source file content
from __future__ import unicode_literals

import importlib
import inspect
import os
import re
import shutil
import sys
import tempfile
from unittest import skipIf

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.template.base import TemplateDoesNotExist
from django.test import RequestFactory, TestCase, override_settings
from django.utils import six
from django.utils.encoding import force_bytes, force_text
from django.views.debug import CallableSettingWrapper, ExceptionReporter

from .. import BrokenException, except_args
from ..views import (
    custom_exception_reporter_filter_view, multivalue_dict_key_error,
    non_sensitive_view, paranoid_view, sensitive_args_function_caller,
    sensitive_kwargs_function_caller, sensitive_method_view, sensitive_view,
)


class CallableSettingWrapperTests(TestCase):
    """ Unittests for CallableSettingWrapper
    """
    def test_repr(self):
        class WrappedCallable(object):
            def __repr__(self):
                return "repr from the wrapped callable"

            def __call__(self):
                pass

        actual = repr(CallableSettingWrapper(WrappedCallable()))
        self.assertEqual(actual, "repr from the wrapped callable")


@override_settings(DEBUG=True, ROOT_URLCONF="view_tests.urls")
class DebugViewTests(TestCase):

    def test_files(self):
        response = self.client.get('/raises/')
        self.assertEqual(response.status_code, 500)

        data = {
            'file_data.txt': SimpleUploadedFile('file_data.txt', b'haha'),
        }
        response = self.client.post('/raises/', data)
        self.assertContains(response, 'file_data.txt', status_code=500)
        self.assertNotContains(response, 'haha', status_code=500)

    def test_400(self):
        # Ensure that when DEBUG=True, technical_500_template() is called.
        response = self.client.get('/raises400/')
        self.assertContains(response, '<div class="context" id="', status_code=400)

    # Ensure no 403.html template exists to test the default case.
    @override_settings(TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
    }])
    def test_403(self):
        response = self.client.get('/raises403/')
        self.assertContains(response, '<h1>403 Forbidden</h1>', status_code=403)

    # Set up a test 403.html template.
    @override_settings(TEMPLATES=[{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'loaders': [
                ('django.template.loaders.locmem.Loader', {
                    '403.html': 'This is a test template for a 403 error.',
                }),
            ],
        },
    }])
    def test_403_template(self):
        response = self.client.get('/raises403/')
        self.assertContains(response, 'test template', status_code=403)

    def test_404(self):
        response = self.client.get('/raises404/')
        self.assertEqual(response.status_code, 404)

    def test_raised_404(self):
        response = self.client.get('/views/raises404/')
        self.assertContains(response, "<code>not-in-urls</code>, didn't match", status_code=404)

    def test_404_not_in_urls(self):
        response = self.client.get('/not-in-urls')
        self.assertNotContains(response, "Raised by:", status_code=404)
        self.assertContains(response, "<code>not-in-urls</code>, didn't match", status_code=404)

    def test_technical_404(self):
        response = self.client.get('/views/technical404/')
        self.assertContains(response, "Raised by:", status_code=404)
        self.assertContains(response, "view_tests.views.technical404", status_code=404)

    def test_classbased_technical_404(self):
        response = self.client.get('/views/classbased404/')
        self.assertContains(response, "Raised by:", status_code=404)
        self.assertContains(response, "view_tests.views.Http404View", status_code=404)

    def test_view_exceptions(self):
        for n in range(len(except_args)):
            self.assertRaises(BrokenException, self.client.get,
                reverse('view_exception', args=(n,)))

    def test_non_l10ned_numeric_ids(self):
        """
        Numeric IDs and fancy traceback context blocks line numbers shouldn't be localized.
        """
        with self.settings(DEBUG=True, USE_L10N=True):
            response = self.client.get('/raises500/')
            # We look for a HTML fragment of the form
            # '<div class="context" id="c38123208">', not '<div class="context" id="c38,123,208"'
            self.assertContains(response, '<div class="context" id="', status_code=500)
            match = re.search(b'<div class="context" id="(?P<id>[^"]+)">', response.content)
            self.assertIsNotNone(match)
            id_repr = match.group('id')
            self.assertFalse(re.search(b'[^c0-9]', id_repr),
                             "Numeric IDs in debug response HTML page shouldn't be localized (value: %s)." % id_repr)

    def test_template_exceptions(self):
        for n in range(len(except_args)):
            try:
                self.client.get(reverse('template_exception', args=(n,)))
            except Exception:
                raising_loc = inspect.trace()[-1][-2][0].strip()
                self.assertNotEqual(raising_loc.find('raise BrokenException'), -1,
                    "Failed to find 'raise BrokenException' in last frame of traceback, instead found: %s" %
                        raising_loc)

    def test_template_loader_postmortem(self):
        """Tests for not existing file"""
        template_name = "notfound.html"
        with tempfile.NamedTemporaryFile(prefix=template_name) as tmpfile:
            tempdir = os.path.dirname(tmpfile.name)
            template_path = os.path.join(tempdir, template_name)
            with override_settings(TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [tempdir],
            }]):
                response = self.client.get(reverse('raises_template_does_not_exist', kwargs={"path": template_name}))
            self.assertContains(response, "%s (File does not exist)" % template_path, status_code=500, count=1)

    @skipIf(sys.platform == "win32", "Python on Windows doesn't have working os.chmod() and os.access().")
    def test_template_loader_postmortem_notreadable(self):
        """Tests for not readable file"""
        with tempfile.NamedTemporaryFile() as tmpfile:
            template_name = tmpfile.name
            tempdir = os.path.dirname(tmpfile.name)
            template_path = os.path.join(tempdir, template_name)
            os.chmod(template_path, 0o0222)
            with override_settings(TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [tempdir],
            }]):
                response = self.client.get(reverse('raises_template_does_not_exist', kwargs={"path": template_name}))
            self.assertContains(response, "%s (File is not readable)" % template_path, status_code=500, count=1)

    def test_template_loader_postmortem_notafile(self):
        """Tests for not being a file"""
        try:
            template_path = tempfile.mkdtemp()
            template_name = os.path.basename(template_path)
            tempdir = os.path.dirname(template_path)
            with override_settings(TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [tempdir],
            }]):
                response = self.client.get(reverse('raises_template_does_not_exist', kwargs={"path": template_name}))
            self.assertContains(response, "%s (Not a file)" % template_path, status_code=500, count=1)
        finally:
            shutil.rmtree(template_path)

    def test_no_template_source_loaders(self):
        """
        Make sure if you don't specify a template, the debug view doesn't blow up.
        """
        self.assertRaises(TemplateDoesNotExist, self.client.get, '/render_no_template/')

    @override_settings(ROOT_URLCONF='view_tests.default_urls')
    def test_default_urlconf_template(self):
        """
        Make sure that the default urlconf template is shown shown instead
        of the technical 404 page, if the user has not altered their
        url conf yet.
        """
        response = self.client.get('/')
        self.assertContains(
            response,
            "<h2>Congratulations on your first Django-powered page.</h2>"
        )

    @override_settings(ROOT_URLCONF='view_tests.regression_21530_urls')
    def test_regression_21530(self):
        """
        Regression test for bug #21530.

        If the admin app include is replaced with exactly one url
        pattern, then the technical 404 template should be displayed.

        The bug here was that an AttributeError caused a 500 response.
        """
        response = self.client.get('/')
        self.assertContains(
            response,
            "Page not found <span>(404)</span>",
            status_code=404
        )


@override_settings(
    DEBUG=True,
    ROOT_URLCONF="view_tests.urls",
    # No template directories are configured, so no templates will be found.
    TEMPLATES=[{
        'BACKEND': 'django.template.backends.dummy.TemplateStrings',
    }],
)
class NonDjangoTemplatesDebugViewTests(TestCase):

    def test_400(self):
        # Ensure that when DEBUG=True, technical_500_template() is called.
        response = self.client.get('/raises400/')
        self.assertContains(response, '<div class="context" id="', status_code=400)

    def test_403(self):
        response = self.client.get('/raises403/')
        self.assertContains(response, '<h1>403 Forbidden</h1>', status_code=403)

    def test_404(self):
        response = self.client.get('/raises404/')
        self.assertEqual(response.status_code, 404)

    def test_template_not_found_error(self):
        # Raises a TemplateDoesNotExist exception and shows the debug view.
        url = reverse('raises_template_does_not_exist', kwargs={"path": "notfound.html"})
        response = self.client.get(url)
        self.assertContains(response, '<div class="context" id="', status_code=500)


class ExceptionReporterTests(TestCase):
    rf = RequestFactory()

    def test_request_and_exception(self):
        "A simple exception report can be generated"
        try:
            request = self.rf.get('/test_view/')
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn('<h1>ValueError at /test_view/</h1>', html)
        self.assertIn('<pre class="exception_value">Can&#39;t find my keys</pre>', html)
        self.assertIn('<th>Request Method:</th>', html)
        self.assertIn('<th>Request URL:</th>', html)
        self.assertIn('<th>Exception Type:</th>', html)
        self.assertIn('<th>Exception Value:</th>', html)
        self.assertIn('<h2>Traceback ', html)
        self.assertIn('<h2>Request information</h2>', html)
        self.assertNotIn('<p>Request data not supplied</p>', html)

    def test_no_request(self):
        "An exception report can be generated without request"
        try:
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn('<h1>ValueError</h1>', html)
        self.assertIn('<pre class="exception_value">Can&#39;t find my keys</pre>', html)
        self.assertNotIn('<th>Request Method:</th>', html)
        self.assertNotIn('<th>Request URL:</th>', html)
        self.assertIn('<th>Exception Type:</th>', html)
        self.assertIn('<th>Exception Value:</th>', html)
        self.assertIn('<h2>Traceback ', html)
        self.assertIn('<h2>Request information</h2>', html)
        self.assertIn('<p>Request data not supplied</p>', html)

    def test_eol_support(self):
        """Test that the ExceptionReporter supports Unix, Windows and Macintosh EOL markers"""
        LINES = list('print %d' % i for i in range(1, 6))
        reporter = ExceptionReporter(None, None, None, None)

        for newline in ['\n', '\r\n', '\r']:
            fd, filename = tempfile.mkstemp(text=False)
            os.write(fd, force_bytes(newline.join(LINES) + newline))
            os.close(fd)

            try:
                self.assertEqual(
                    reporter._get_lines_from_file(filename, 3, 2),
                    (1, LINES[1:3], LINES[3], LINES[4:])
                )
            finally:
                os.unlink(filename)

    def test_no_exception(self):
        "An exception report can be generated for just a request"
        request = self.rf.get('/test_view/')
        reporter = ExceptionReporter(request, None, None, None)
        html = reporter.get_traceback_html()
        self.assertIn('<h1>Report at /test_view/</h1>', html)
        self.assertIn('<pre class="exception_value">No exception message supplied</pre>', html)
        self.assertIn('<th>Request Method:</th>', html)
        self.assertIn('<th>Request URL:</th>', html)
        self.assertNotIn('<th>Exception Type:</th>', html)
        self.assertNotIn('<th>Exception Value:</th>', html)
        self.assertNotIn('<h2>Traceback ', html)
        self.assertIn('<h2>Request information</h2>', html)
        self.assertNotIn('<p>Request data not supplied</p>', html)

    def test_request_and_message(self):
        "A message can be provided in addition to a request"
        request = self.rf.get('/test_view/')
        reporter = ExceptionReporter(request, None, "I'm a little teapot", None)
        html = reporter.get_traceback_html()
        self.assertIn('<h1>Report at /test_view/</h1>', html)
        self.assertIn('<pre class="exception_value">I&#39;m a little teapot</pre>', html)
        self.assertIn('<th>Request Method:</th>', html)
        self.assertIn('<th>Request URL:</th>', html)
        self.assertNotIn('<th>Exception Type:</th>', html)
        self.assertNotIn('<th>Exception Value:</th>', html)
        self.assertNotIn('<h2>Traceback ', html)
        self.assertIn('<h2>Request information</h2>', html)
        self.assertNotIn('<p>Request data not supplied</p>', html)

    def test_message_only(self):
        reporter = ExceptionReporter(None, None, "I'm a little teapot", None)
        html = reporter.get_traceback_html()
        self.assertIn('<h1>Report</h1>', html)
        self.assertIn('<pre class="exception_value">I&#39;m a little teapot</pre>', html)
        self.assertNotIn('<th>Request Method:</th>', html)
        self.assertNotIn('<th>Request URL:</th>', html)
        self.assertNotIn('<th>Exception Type:</th>', html)
        self.assertNotIn('<th>Exception Value:</th>', html)
        self.assertNotIn('<h2>Traceback ', html)
        self.assertIn('<h2>Request information</h2>', html)
        self.assertIn('<p>Request data not supplied</p>', html)

    def test_non_utf8_values_handling(self):
        "Non-UTF-8 exceptions/values should not make the output generation choke."
        try:
            class NonUtf8Output(Exception):
                def __repr__(self):
                    return b'EXC\xe9EXC'
            somevar = b'VAL\xe9VAL'  # NOQA
            raise NonUtf8Output()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn('VAL\\xe9VAL', html)
        self.assertIn('EXC\\xe9EXC', html)

    def test_unprintable_values_handling(self):
        "Unprintable values should not make the output generation choke."
        try:
            class OomOutput(object):
                def __repr__(self):
                    raise MemoryError('OOM')
            oomvalue = OomOutput()  # NOQA
            raise ValueError()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn('<td class="code"><pre>Error in formatting', html)

    def test_too_large_values_handling(self):
        "Large values should not create a large HTML."
        large = 256 * 1024
        repr_of_str_adds = len(repr(''))
        try:
            class LargeOutput(object):
                def __repr__(self):
                    return repr('A' * large)
            largevalue = LargeOutput()  # NOQA
            raise ValueError()
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertEqual(len(html) // 1024 // 128, 0)  # still fit in 128Kb
        self.assertIn('&lt;trimmed %d bytes string&gt;' % (large + repr_of_str_adds,), html)

    @skipIf(six.PY2, 'Bug manifests on PY3 only')
    def test_unfrozen_importlib(self):
        """
        importlib is not a frozen app, but its loader thinks it's frozen which
        results in an ImportError on Python 3. Refs #21443.
        """
        try:
            request = self.rf.get('/test_view/')
            importlib.import_module('abc.def.invalid.name')
        except Exception:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        html = reporter.get_traceback_html()
        self.assertIn('<h1>ImportError at /test_view/</h1>', html)


class PlainTextReportTests(TestCase):
    rf = RequestFactory()

    def test_request_and_exception(self):
        "A simple exception report can be generated"
        try:
            request = self.rf.get('/test_view/')
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(request, exc_type, exc_value, tb)
        text = reporter.get_traceback_text()
        self.assertIn('ValueError at /test_view/', text)
        self.assertIn("Can't find my keys", text)
        self.assertIn('Request Method:', text)
        self.assertIn('Request URL:', text)
        self.assertIn('Exception Type:', text)
        self.assertIn('Exception Value:', text)
        self.assertIn('Traceback:', text)
        self.assertIn('Request information:', text)
        self.assertNotIn('Request data not supplied', text)

    def test_no_request(self):
        "An exception report can be generated without request"
        try:
            raise ValueError("Can't find my keys")
        except ValueError:
            exc_type, exc_value, tb = sys.exc_info()
        reporter = ExceptionReporter(None, exc_type, exc_value, tb)
        text = reporter.get_traceback_text()
        self.assertIn('ValueError', text)
        self.assertIn("Can't find my keys", text)
        self.assertNotIn('Request Method:', text)
        self.assertNotIn('Request URL:', text)
        self.assertIn('Exception Type:', text)
        self.assertIn('Exception Value:', text)
        self.assertIn('Traceback:', text)
        self.assertIn('Request data not supplied', text)

    def test_no_exception(self):
        "An exception report can be generated for just a request"
        request = self.rf.get('/test_view/')
        reporter = ExceptionReporter(request, None, None, None)
        reporter.get_traceback_text()

    def test_request_and_message(self):
        "A message can be provided in addition to a request"
        request = self.rf.get('/test_view/')
        reporter = ExceptionReporter(request, None, "I'm a little teapot", None)
        reporter.get_traceback_text()

    def test_message_only(self):
        reporter = ExceptionReporter(None, None, "I'm a little teapot", None)
        reporter.get_traceback_text()


class ExceptionReportTestMixin(object):

    # Mixin used in the ExceptionReporterFilterTests and
    # AjaxResponseExceptionReporterFilter tests below

    breakfast_data = {'sausage-key': 'sausage-value',
                      'baked-beans-key': 'baked-beans-value',
                      'hash-brown-key': 'hash-brown-value',
                      'bacon-key': 'bacon-value'}

    def verify_unsafe_response(self, view, check_for_vars=True,
                               check_for_POST_params=True):
        """
        Asserts that potentially sensitive info are displayed in the response.
        """
        request = self.rf.post('/some_url/', self.breakfast_data)
        response = view(request)
        if check_for_vars:
            # All variables are shown.
            self.assertContains(response, 'cooked_eggs', status_code=500)
            self.assertContains(response, 'scrambled', status_code=500)
            self.assertContains(response, 'sauce', status_code=500)
            self.assertContains(response, 'worcestershire', status_code=500)
        if check_for_POST_params:
            for k, v in self.breakfast_data.items():
                # All POST parameters are shown.
                self.assertContains(response, k, status_code=500)
                self.assertContains(response, v, status_code=500)

    def verify_safe_response(self, view, check_for_vars=True,
                             check_for_POST_params=True):
        """
        Asserts that certain sensitive info are not displayed in the response.
        """
        request = self.rf.post('/some_url/', self.breakfast_data)
        response = view(request)
        if check_for_vars:
            # Non-sensitive variable's name and value are shown.
            self.assertContains(response, 'cooked_eggs', status_code=500)
            self.assertContains(response, 'scrambled', status_code=500)
            # Sensitive variable's name is shown but not its value.
            self.assertContains(response, 'sauce', status_code=500)
            self.assertNotContains(response, 'worcestershire', status_code=500)
        if check_for_POST_params:
            for k, v in self.breakfast_data.items():
                # All POST parameters' names are shown.
                self.assertContains(response, k, status_code=500)
            # Non-sensitive POST parameters' values are shown.
            self.assertContains(response, 'baked-beans-value', status_code=500)
            self.assertContains(response, 'hash-brown-value', status_code=500)
            # Sensitive POST parameters' values are not shown.
            self.assertNotContains(response, 'sausage-value', status_code=500)
            self.assertNotContains(response, 'bacon-value', status_code=500)

    def verify_paranoid_response(self, view, check_for_vars=True,
                                 check_for_POST_params=True):
        """
        Asserts that no variables or POST parameters are displayed in the response.
        """
        request = self.rf.post('/some_url/', self.breakfast_data)
        response = view(request)
        if check_for_vars:
            # Show variable names but not their values.
            self.assertContains(response, 'cooked_eggs', status_code=500)
            self.assertNotContains(response, 'scrambled', status_code=500)
            self.assertContains(response, 'sauce', status_code=500)
            self.assertNotContains(response, 'worcestershire', status_code=500)
        if check_for_POST_params:
            for k, v in self.breakfast_data.items():
                # All POST parameters' names are shown.
                self.assertContains(response, k, status_code=500)
                # No POST parameters' values are shown.
                self.assertNotContains(response, v, status_code=500)

    def verify_unsafe_email(self, view, check_for_POST_params=True):
        """
        Asserts that potentially sensitive info are displayed in the email report.
        """
        with self.settings(ADMINS=(('Admin', 'admin@fattie-breakie.com'),)):
            mail.outbox = []  # Empty outbox
            request = self.rf.post('/some_url/', self.breakfast_data)
            view(request)
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]

            # Frames vars are never shown in plain text email reports.
            body_plain = force_text(email.body)
            self.assertNotIn('cooked_eggs', body_plain)
            self.assertNotIn('scrambled', body_plain)
            self.assertNotIn('sauce', body_plain)
            self.assertNotIn('worcestershire', body_plain)

            # Frames vars are shown in html email reports.
            body_html = force_text(email.alternatives[0][0])
            self.assertIn('cooked_eggs', body_html)
            self.assertIn('scrambled', body_html)
            self.assertIn('sauce', body_html)
            self.assertIn('worcestershire', body_html)

            if check_for_POST_params:
                for k, v in self.breakfast_data.items():
                    # All POST parameters are shown.
                    self.assertIn(k, body_plain)
                    self.assertIn(v, body_plain)
                    self.assertIn(k, body_html)
                    self.assertIn(v, body_html)

    def verify_safe_email(self, view, check_for_POST_params=True):
        """
        Asserts that certain sensitive info are not displayed in the email report.
        """
        with self.settings(ADMINS=(('Admin', 'admin@fattie-breakie.com'),)):
            mail.outbox = []  # Empty outbox
            request = self.rf.post('/some_url/', self.breakfast_data)
            view(request)
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]

            # Frames vars are never shown in plain text email reports.
            body_plain = force_text(email.body)
            self.assertNotIn('cooked_eggs', body_plain)
            self.assertNotIn('scrambled', body_plain)
            self.assertNotIn('sauce', body_plain)
            self.assertNotIn('worcestershire', body_plain)

            # Frames vars are shown in html email reports.
            body_html = force_text(email.alternatives[0][0])
            self.assertIn('cooked_eggs', body_html)
            self.assertIn('scrambled', body_html)
            self.assertIn('sauce', body_html)
            self.assertNotIn('worcestershire', body_html)

            if check_for_POST_params:
                for k, v in self.breakfast_data.items():
                    # All POST parameters' names are shown.
                    self.assertIn(k, body_plain)
                # Non-sensitive POST parameters' values are shown.
                self.assertIn('baked-beans-value', body_plain)
                self.assertIn('hash-brown-value', body_plain)
                self.assertIn('baked-beans-value', body_html)
                self.assertIn('hash-brown-value', body_html)
                # Sensitive POST parameters' values are not shown.
                self.assertNotIn('sausage-value', body_plain)
                self.assertNotIn('bacon-value', body_plain)
                self.assertNotIn('sausage-value', body_html)
                self.assertNotIn('bacon-value', body_html)

    def verify_paranoid_email(self, view):
        """
        Asserts that no variables or POST parameters are displayed in the email report.
        """
        with self.settings(ADMINS=(('Admin', 'admin@fattie-breakie.com'),)):
            mail.outbox = []  # Empty outbox
            request = self.rf.post('/some_url/', self.breakfast_data)
            view(request)
            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            # Frames vars are never shown in plain text email reports.
            body = force_text(email.body)
            self.assertNotIn('cooked_eggs', body)
            self.assertNotIn('scrambled', body)
            self.assertNotIn('sauce', body)
            self.assertNotIn('worcestershire', body)
            for k, v in self.breakfast_data.items():
                # All POST parameters' names are shown.
                self.assertIn(k, body)
                # No POST parameters' values are shown.
                self.assertNotIn(v, body)


@override_settings(ROOT_URLCONF='view_tests.urls')
class ExceptionReporterFilterTests(TestCase, ExceptionReportTestMixin):
    """
    Ensure that sensitive information can be filtered out of error reports.
    Refs #14614.
    """
    rf = RequestFactory()

    def test_non_sensitive_request(self):
        """
        Ensure that everything (request info and frame variables) can bee seen
        in the default error reports for non-sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(non_sensitive_view)
            self.verify_unsafe_email(non_sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(non_sensitive_view)
            self.verify_unsafe_email(non_sensitive_view)

    def test_sensitive_request(self):
        """
        Ensure that sensitive POST parameters and frame variables cannot be
        seen in the default error reports for sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_view)
            self.verify_unsafe_email(sensitive_view)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_view)
            self.verify_safe_email(sensitive_view)

    def test_paranoid_request(self):
        """
        Ensure that no POST parameters and frame variables can be seen in the
        default error reports for "paranoid" requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(paranoid_view)
            self.verify_unsafe_email(paranoid_view)

        with self.settings(DEBUG=False):
            self.verify_paranoid_response(paranoid_view)
            self.verify_paranoid_email(paranoid_view)

    def test_multivalue_dict_key_error(self):
        """
        #21098 -- Ensure that sensitive POST parameters cannot be seen in the
        error reports for if request.POST['nonexistent_key'] throws an error.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(multivalue_dict_key_error)
            self.verify_unsafe_email(multivalue_dict_key_error)

        with self.settings(DEBUG=False):
            self.verify_safe_response(multivalue_dict_key_error)
            self.verify_safe_email(multivalue_dict_key_error)

    def test_custom_exception_reporter_filter(self):
        """
        Ensure that it's possible to assign an exception reporter filter to
        the request to bypass the one set in DEFAULT_EXCEPTION_REPORTER_FILTER.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(custom_exception_reporter_filter_view)
            self.verify_unsafe_email(custom_exception_reporter_filter_view)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(custom_exception_reporter_filter_view)
            self.verify_unsafe_email(custom_exception_reporter_filter_view)

    def test_sensitive_method(self):
        """
        Ensure that the sensitive_variables decorator works with object
        methods.
        Refs #18379.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_method_view,
                                        check_for_POST_params=False)
            self.verify_unsafe_email(sensitive_method_view,
                                     check_for_POST_params=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_method_view,
                                      check_for_POST_params=False)
            self.verify_safe_email(sensitive_method_view,
                                   check_for_POST_params=False)

    def test_sensitive_function_arguments(self):
        """
        Ensure that sensitive variables don't leak in the sensitive_variables
        decorator's frame, when those variables are passed as arguments to the
        decorated function.
        Refs #19453.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_args_function_caller)
            self.verify_unsafe_email(sensitive_args_function_caller)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_args_function_caller, check_for_POST_params=False)
            self.verify_safe_email(sensitive_args_function_caller, check_for_POST_params=False)

    def test_sensitive_function_keyword_arguments(self):
        """
        Ensure that sensitive variables don't leak in the sensitive_variables
        decorator's frame, when those variables are passed as keyword arguments
        to the decorated function.
        Refs #19453.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_kwargs_function_caller)
            self.verify_unsafe_email(sensitive_kwargs_function_caller)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_kwargs_function_caller, check_for_POST_params=False)
            self.verify_safe_email(sensitive_kwargs_function_caller, check_for_POST_params=False)

    def test_callable_settings(self):
        """
        Callable settings should not be evaluated in the debug page (#21345).
        """
        def callable_setting():
            return "This should not be displayed"
        with self.settings(DEBUG=True, FOOBAR=callable_setting):
            response = self.client.get('/raises500/')
            self.assertNotContains(response, "This should not be displayed", status_code=500)

    def test_callable_settings_forbidding_to_set_attributes(self):
        """
        Callable settings which forbid to set attributes should not break
        the debug page (#23070).
        """
        class CallableSettingWithSlots(object):
            __slots__ = []

            def __call__(self):
                return "This should not be displayed"

        with self.settings(DEBUG=True, WITH_SLOTS=CallableSettingWithSlots()):
            response = self.client.get('/raises500/')
            self.assertNotContains(response, "This should not be displayed", status_code=500)

    def test_dict_setting_with_non_str_key(self):
        """
        A dict setting containing a non-string key should not break the
        debug page (#12744).
        """
        with self.settings(DEBUG=True, FOOBAR={42: None}):
            response = self.client.get('/raises500/')
            self.assertContains(response, 'FOOBAR', status_code=500)

    def test_sensitive_settings(self):
        """
        The debug page should not show some sensitive settings
        (password, secret key, ...).
        """
        sensitive_settings = [
            'SECRET_KEY',
            'PASSWORD',
            'API_KEY',
            'AUTH_TOKEN',
        ]
        for setting in sensitive_settings:
            with self.settings(DEBUG=True, **{setting: "should not be displayed"}):
                response = self.client.get('/raises500/')
                self.assertNotContains(response, 'should not be displayed', status_code=500)

    def test_settings_with_sensitive_keys(self):
        """
        The debug page should filter out some sensitive information found in
        dict settings.
        """
        sensitive_settings = [
            'SECRET_KEY',
            'PASSWORD',
            'API_KEY',
            'AUTH_TOKEN',
        ]
        for setting in sensitive_settings:
            FOOBAR = {
                setting: "should not be displayed",
                'recursive': {setting: "should not be displayed"},
            }
            with self.settings(DEBUG=True, FOOBAR=FOOBAR):
                response = self.client.get('/raises500/')
                self.assertNotContains(response, 'should not be displayed', status_code=500)


class AjaxResponseExceptionReporterFilter(TestCase, ExceptionReportTestMixin):
    """
    Ensure that sensitive information can be filtered out of error reports.

    Here we specifically test the plain text 500 debug-only error page served
    when it has been detected the request was sent by JS code. We don't check
    for (non)existence of frames vars in the traceback information section of
    the response content because we don't include them in these error pages.
    Refs #14614.
    """
    rf = RequestFactory(HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_non_sensitive_request(self):
        """
        Ensure that request info can bee seen in the default error reports for
        non-sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(non_sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(non_sensitive_view, check_for_vars=False)

    def test_sensitive_request(self):
        """
        Ensure that sensitive POST parameters cannot be seen in the default
        error reports for sensitive requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(sensitive_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_safe_response(sensitive_view, check_for_vars=False)

    def test_paranoid_request(self):
        """
        Ensure that no POST parameters can be seen in the default error reports
        for "paranoid" requests.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(paranoid_view, check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_paranoid_response(paranoid_view, check_for_vars=False)

    def test_custom_exception_reporter_filter(self):
        """
        Ensure that it's possible to assign an exception reporter filter to
        the request to bypass the one set in DEFAULT_EXCEPTION_REPORTER_FILTER.
        """
        with self.settings(DEBUG=True):
            self.verify_unsafe_response(custom_exception_reporter_filter_view,
                check_for_vars=False)

        with self.settings(DEBUG=False):
            self.verify_unsafe_response(custom_exception_reporter_filter_view,
                check_for_vars=False)
