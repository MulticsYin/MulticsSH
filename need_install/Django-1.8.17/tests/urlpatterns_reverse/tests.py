# -*- coding: utf-8 -*-
"""
Unit tests for reverse URL lookups.
"""
from __future__ import unicode_literals

import sys
import unittest

from admin_scripts.tests import AdminScriptTestCase

from django.conf import settings
from django.conf.urls import include
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, ViewDoesNotExist
from django.core.urlresolvers import (
    NoReverseMatch, RegexURLPattern, RegexURLResolver, Resolver404,
    ResolverMatch, get_callable, get_resolver, resolve, reverse, reverse_lazy,
)
from django.http import (
    HttpRequest, HttpResponsePermanentRedirect, HttpResponseRedirect,
)
from django.shortcuts import redirect
from django.test import (
    SimpleTestCase, TestCase, ignore_warnings, override_settings,
)
from django.utils import six
from django.utils.deprecation import RemovedInDjango110Warning

from . import middleware, urlconf_outer, views
from .views import empty_view

resolve_test_data = (
    # These entries are in the format: (path, url_name, app_name, namespace, view_name, func, args, kwargs)
    # Simple case
    ('/normal/42/37/', 'normal-view', None, '', 'normal-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/view_class/42/37/', 'view-class', None, '', 'view-class', views.view_class_instance, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/included/normal/42/37/', 'inc-normal-view', None, '', 'inc-normal-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/included/view_class/42/37/', 'inc-view-class', None, '', 'inc-view-class', views.view_class_instance, tuple(), {'arg1': '42', 'arg2': '37'}),

    # Unnamed args are dropped if you have *any* kwargs in a pattern
    ('/mixed_args/42/37/', 'mixed-args', None, '', 'mixed-args', views.empty_view, tuple(), {'arg2': '37'}),
    ('/included/mixed_args/42/37/', 'inc-mixed-args', None, '', 'inc-mixed-args', views.empty_view, tuple(), {'arg2': '37'}),

    # Unnamed views should have None as the url_name. Regression data for #21157.
    ('/unnamed/normal/42/37/', None, None, '', 'urlpatterns_reverse.views.empty_view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/unnamed/view_class/42/37/', None, None, '', 'urlpatterns_reverse.views.ViewClass', views.view_class_instance, tuple(), {'arg1': '42', 'arg2': '37'}),

    # If you have no kwargs, you get an args list.
    ('/no_kwargs/42/37/', 'no-kwargs', None, '', 'no-kwargs', views.empty_view, ('42', '37'), {}),
    ('/included/no_kwargs/42/37/', 'inc-no-kwargs', None, '', 'inc-no-kwargs', views.empty_view, ('42', '37'), {}),

    # Namespaces
    ('/test1/inner/42/37/', 'urlobject-view', 'testapp', 'test-ns1', 'test-ns1:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/included/test3/inner/42/37/', 'urlobject-view', 'testapp', 'test-ns3', 'test-ns3:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/ns-included1/normal/42/37/', 'inc-normal-view', None, 'inc-ns1', 'inc-ns1:inc-normal-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/included/test3/inner/42/37/', 'urlobject-view', 'testapp', 'test-ns3', 'test-ns3:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/default/inner/42/37/', 'urlobject-view', 'testapp', 'testapp', 'testapp:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/other2/inner/42/37/', 'urlobject-view', 'nodefault', 'other-ns2', 'other-ns2:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/other1/inner/42/37/', 'urlobject-view', 'nodefault', 'other-ns1', 'other-ns1:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),

    # Nested namespaces
    ('/ns-included1/test3/inner/42/37/', 'urlobject-view', 'testapp', 'inc-ns1:test-ns3', 'inc-ns1:test-ns3:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),
    ('/ns-included1/ns-included4/ns-included2/test3/inner/42/37/', 'urlobject-view', 'testapp', 'inc-ns1:inc-ns4:inc-ns2:test-ns3', 'inc-ns1:inc-ns4:inc-ns2:test-ns3:urlobject-view', views.empty_view, tuple(), {'arg1': '42', 'arg2': '37'}),

    # Namespaces capturing variables
    ('/inc70/', 'inner-nothing', None, 'inc-ns5', 'inc-ns5:inner-nothing', views.empty_view, tuple(), {'outer': '70'}),
    ('/inc78/extra/foobar/', 'inner-extra', None, 'inc-ns5', 'inc-ns5:inner-extra', views.empty_view, tuple(), {'outer': '78', 'extra': 'foobar'}),
)

test_data = (
    ('places', '/places/3/', [3], {}),
    ('places', '/places/3/', ['3'], {}),
    ('places', NoReverseMatch, ['a'], {}),
    ('places', NoReverseMatch, [], {}),
    ('places?', '/place/', [], {}),
    ('places+', '/places/', [], {}),
    ('places*', '/place/', [], {}),
    ('places2?', '/', [], {}),
    ('places2+', '/places/', [], {}),
    ('places2*', '/', [], {}),
    ('places3', '/places/4/', [4], {}),
    ('places3', '/places/harlem/', ['harlem'], {}),
    ('places3', NoReverseMatch, ['harlem64'], {}),
    ('places4', '/places/3/', [], {'id': 3}),
    ('people', NoReverseMatch, [], {}),
    ('people', '/people/adrian/', ['adrian'], {}),
    ('people', '/people/adrian/', [], {'name': 'adrian'}),
    ('people', NoReverseMatch, ['name with spaces'], {}),
    ('people', NoReverseMatch, [], {'name': 'name with spaces'}),
    ('people2', '/people/name/', [], {}),
    ('people2a', '/people/name/fred/', ['fred'], {}),
    ('people_backref', '/people/nate-nate/', ['nate'], {}),
    ('people_backref', '/people/nate-nate/', [], {'name': 'nate'}),
    ('optional', '/optional/fred/', [], {'name': 'fred'}),
    ('optional', '/optional/fred/', ['fred'], {}),
    ('named_optional', '/optional/1/', [1], {}),
    ('named_optional', '/optional/1/', [], {'arg1': 1}),
    ('named_optional', '/optional/1/2/', [1, 2], {}),
    ('named_optional', '/optional/1/2/', [], {'arg1': 1, 'arg2': 2}),
    ('named_optional_terminated', '/optional/1/2/', [1, 2], {}),
    ('named_optional_terminated', '/optional/1/2/', [], {'arg1': 1, 'arg2': 2}),
    ('hardcoded', '/hardcoded/', [], {}),
    ('hardcoded2', '/hardcoded/doc.pdf', [], {}),
    ('people3', '/people/il/adrian/', [], {'state': 'il', 'name': 'adrian'}),
    ('people3', NoReverseMatch, [], {'state': 'il'}),
    ('people3', NoReverseMatch, [], {'name': 'adrian'}),
    ('people4', NoReverseMatch, [], {'state': 'il', 'name': 'adrian'}),
    ('people6', '/people/il/test/adrian/', ['il/test', 'adrian'], {}),
    ('people6', '/people//adrian/', ['adrian'], {}),
    ('range', '/character_set/a/', [], {}),
    ('range2', '/character_set/x/', [], {}),
    ('price', '/price/$10/', ['10'], {}),
    ('price2', '/price/$10/', ['10'], {}),
    ('price3', '/price/$10/', ['10'], {}),
    ('product', '/product/chocolate+($2.00)/', [], {'price': '2.00', 'product': 'chocolate'}),
    ('headlines', '/headlines/2007.5.21/', [], dict(year=2007, month=5, day=21)),
    ('windows', r'/windows_path/C:%5CDocuments%20and%20Settings%5Cspam/', [], dict(drive_name='C', path=r'Documents and Settings\spam')),
    ('special', r'/special_chars/~@+%5C$*%7C/', [r'~@+\$*|'], {}),
    ('special', r'/special_chars/some%20resource/', [r'some resource'], {}),
    ('special', r'/special_chars/10%25%20complete/', [r'10% complete'], {}),
    ('special', r'/special_chars/some%20resource/', [], {'chars': r'some resource'}),
    ('special', r'/special_chars/10%25%20complete/', [], {'chars': r'10% complete'}),
    ('special', NoReverseMatch, [''], {}),
    ('mixed', '/john/0/', [], {'name': 'john'}),
    ('repeats', '/repeats/a/', [], {}),
    ('repeats2', '/repeats/aa/', [], {}),
    ('repeats3', '/repeats/aa/', [], {}),
    ('insensitive', '/CaseInsensitive/fred', ['fred'], {}),
    ('test', '/test/1', [], {}),
    ('test2', '/test/2', [], {}),
    ('inner-nothing', '/outer/42/', [], {'outer': '42'}),
    ('inner-nothing', '/outer/42/', ['42'], {}),
    ('inner-nothing', NoReverseMatch, ['foo'], {}),
    ('inner-extra', '/outer/42/extra/inner/', [], {'extra': 'inner', 'outer': '42'}),
    ('inner-extra', '/outer/42/extra/inner/', ['42', 'inner'], {}),
    ('inner-extra', NoReverseMatch, ['fred', 'inner'], {}),
    ('inner-no-kwargs', '/outer-no-kwargs/42/inner-no-kwargs/1/', ['42', '1'], {}),
    ('disjunction', NoReverseMatch, ['foo'], {}),
    ('inner-disjunction', NoReverseMatch, ['10', '11'], {}),
    ('extra-places', '/e-places/10/', ['10'], {}),
    ('extra-people', '/e-people/fred/', ['fred'], {}),
    ('extra-people', '/e-people/fred/', [], {'name': 'fred'}),
    ('part', '/part/one/', [], {'value': 'one'}),
    ('part', '/prefix/xx/part/one/', [], {'value': 'one', 'prefix': 'xx'}),
    ('part2', '/part2/one/', [], {'value': 'one'}),
    ('part2', '/part2/', [], {}),
    ('part2', '/prefix/xx/part2/one/', [], {'value': 'one', 'prefix': 'xx'}),
    ('part2', '/prefix/xx/part2/', [], {'prefix': 'xx'}),

    # Tests for nested groups. Nested capturing groups will only work if you
    # *only* supply the correct outer group.
    ('nested-noncapture', '/nested/noncapture/opt', [], {'p': 'opt'}),
    ('nested-capture', '/nested/capture/opt/', ['opt/'], {}),
    ('nested-capture', NoReverseMatch, [], {'p': 'opt'}),
    ('nested-mixedcapture', '/nested/capture/mixed/opt', ['opt'], {}),
    ('nested-mixedcapture', NoReverseMatch, [], {'p': 'opt'}),
    ('nested-namedcapture', '/nested/capture/named/opt/', [], {'outer': 'opt/'}),
    ('nested-namedcapture', NoReverseMatch, [], {'outer': 'opt/', 'inner': 'opt'}),
    ('nested-namedcapture', NoReverseMatch, [], {'inner': 'opt'}),

    # Regression for #9038
    # These views are resolved by method name. Each method is deployed twice -
    # once with an explicit argument, and once using the default value on
    # the method. This is potentially ambiguous, as you have to pick the
    # correct view for the arguments provided.
    ('urlpatterns_reverse.views.absolute_kwargs_view', '/absolute_arg_view/', [], {}),
    ('urlpatterns_reverse.views.absolute_kwargs_view', '/absolute_arg_view/10/', [], {'arg1': 10}),
    ('non_path_include', '/includes/non_path_include/', [], {}),

    # Tests for #13154
    ('defaults', '/defaults_view1/3/', [], {'arg1': 3, 'arg2': 1}),
    ('defaults', '/defaults_view2/3/', [], {'arg1': 3, 'arg2': 2}),
    ('defaults', NoReverseMatch, [], {'arg1': 3, 'arg2': 3}),
    ('defaults', NoReverseMatch, [], {'arg2': 1}),

    # Security tests
    ('security', '/%2Fexample.com/security/', ['/example.com'], {}),
)


@override_settings(ROOT_URLCONF='urlpatterns_reverse.no_urls')
class NoURLPatternsTests(TestCase):

    def test_no_urls_exception(self):
        """
        RegexURLResolver should raise an exception when no urlpatterns exist.
        """
        resolver = RegexURLResolver(r'^$', settings.ROOT_URLCONF)

        self.assertRaisesMessage(ImproperlyConfigured,
            "The included urlconf 'urlpatterns_reverse.no_urls' does not "
            "appear to have any patterns in it. If you see valid patterns in "
            "the file then the issue is probably caused by a circular import.",
            getattr, resolver, 'url_patterns')


@override_settings(ROOT_URLCONF='urlpatterns_reverse.urls')
class URLPatternReverse(TestCase):

    @ignore_warnings(category=RemovedInDjango110Warning)
    def test_urlpattern_reverse(self):
        for name, expected, args, kwargs in test_data:
            try:
                got = reverse(name, args=args, kwargs=kwargs)
            except NoReverseMatch:
                self.assertEqual(expected, NoReverseMatch)
            else:
                self.assertEqual(got, expected)

    def test_reverse_none(self):
        # Reversing None should raise an error, not return the last un-named view.
        self.assertRaises(NoReverseMatch, reverse, None)

    def test_prefix_braces(self):
        self.assertEqual('/%7B%7Binvalid%7D%7D/includes/non_path_include/',
               reverse('non_path_include', prefix='/{{invalid}}/'))

    def test_prefix_parenthesis(self):
        self.assertEqual('/bogus%29/includes/non_path_include/',
               reverse('non_path_include', prefix='/bogus)/'))

    def test_prefix_format_char(self):
        self.assertEqual('/bump%2520map/includes/non_path_include/',
               reverse('non_path_include', prefix='/bump%20map/'))

    def test_non_urlsafe_prefix_with_args(self):
        # Regression for #20022
        self.assertEqual('/%7Eme/places/1/',
                reverse('places', args=[1], prefix='/~me/'))

    def test_patterns_reported(self):
        # Regression for #17076
        try:
            # this url exists, but requires an argument
            reverse("people", args=[])
        except NoReverseMatch as e:
            pattern_description = r"1 pattern(s) tried: ['people/(?P<name>\\w+)/$']"
            self.assertIn(pattern_description, str(e))
        else:
            # we can't use .assertRaises, since we want to inspect the
            # exception
            self.fail("Expected a NoReverseMatch, but none occurred.")

    def test_reverse_returns_unicode(self):
        name, expected, args, kwargs = test_data[0]
        self.assertIsInstance(
            reverse(name, args=args, kwargs=kwargs),
            six.text_type
        )


class ResolverTests(unittest.TestCase):
    def test_resolver_repr(self):
        """
        Test repr of RegexURLResolver, especially when urlconf_name is a list
        (#17892).
        """
        # Pick a resolver from a namespaced urlconf
        resolver = get_resolver('urlpatterns_reverse.namespace_urls')
        sub_resolver = resolver.namespace_dict['test-ns1'][1]
        self.assertIn('<RegexURLPattern list>', repr(sub_resolver))

    def test_reverse_lazy_object_coercion_by_resolve(self):
        """
        Verifies lazy object returned by reverse_lazy is coerced to
        text by resolve(). Previous to #21043, this would raise a TypeError.
        """
        urls = 'urlpatterns_reverse.named_urls'
        proxy_url = reverse_lazy('named-url1', urlconf=urls)
        resolver = get_resolver(urls)
        try:
            resolver.resolve(proxy_url)
        except TypeError:
            self.fail('Failed to coerce lazy object to text')

    def test_non_regex(self):
        """
        Verifies that we raise a Resolver404 if what we are resolving doesn't
        meet the basic requirements of a path to match - i.e., at the very
        least, it matches the root pattern '^/'. We must never return None
        from resolve, or we will get a TypeError further down the line.

        Regression for #10834.
        """
        self.assertRaises(Resolver404, resolve, '')
        self.assertRaises(Resolver404, resolve, 'a')
        self.assertRaises(Resolver404, resolve, '\\')
        self.assertRaises(Resolver404, resolve, '.')

    def test_404_tried_urls_have_names(self):
        """
        Verifies that the list of URLs that come back from a Resolver404
        exception contains a list in the right format for printing out in
        the DEBUG 404 page with both the patterns and URL names, if available.
        """
        urls = 'urlpatterns_reverse.named_urls'
        # this list matches the expected URL types and names returned when
        # you try to resolve a non-existent URL in the first level of included
        # URLs in named_urls.py (e.g., '/included/non-existent-url')
        url_types_names = [
            [{'type': RegexURLPattern, 'name': 'named-url1'}],
            [{'type': RegexURLPattern, 'name': 'named-url2'}],
            [{'type': RegexURLPattern, 'name': None}],
            [{'type': RegexURLResolver}, {'type': RegexURLPattern, 'name': 'named-url3'}],
            [{'type': RegexURLResolver}, {'type': RegexURLPattern, 'name': 'named-url4'}],
            [{'type': RegexURLResolver}, {'type': RegexURLPattern, 'name': None}],
            [{'type': RegexURLResolver}, {'type': RegexURLResolver}],
        ]
        try:
            resolve('/included/non-existent-url', urlconf=urls)
            self.fail('resolve did not raise a 404')
        except Resolver404 as e:
            # make sure we at least matched the root ('/') url resolver:
            self.assertIn('tried', e.args[0])
            tried = e.args[0]['tried']
            self.assertEqual(len(e.args[0]['tried']), len(url_types_names), 'Wrong number of tried URLs returned.  Expected %s, got %s.' % (len(url_types_names), len(e.args[0]['tried'])))
            for tried, expected in zip(e.args[0]['tried'], url_types_names):
                for t, e in zip(tried, expected):
                    self.assertIsInstance(t, e['type']), str('%s is not an instance of %s') % (t, e['type'])
                    if 'name' in e:
                        if not e['name']:
                            self.assertIsNone(t.name, 'Expected no URL name but found %s.' % t.name)
                        else:
                            self.assertEqual(t.name, e['name'], 'Wrong URL name.  Expected "%s", got "%s".' % (e['name'], t.name))


@override_settings(ROOT_URLCONF='urlpatterns_reverse.reverse_lazy_urls')
class ReverseLazyTest(TestCase):

    def test_redirect_with_lazy_reverse(self):
        response = self.client.get('/redirect/')
        self.assertRedirects(response, "/redirected_to/", status_code=301)

    def test_user_permission_with_lazy_reverse(self):
        User.objects.create_user('alfred', 'alfred@example.com', password='testpw')
        response = self.client.get('/login_required_view/')
        self.assertRedirects(response, "/login/?next=/login_required_view/", status_code=302)
        self.client.login(username='alfred', password='testpw')
        response = self.client.get('/login_required_view/')
        self.assertEqual(response.status_code, 200)

    def test_inserting_reverse_lazy_into_string(self):
        self.assertEqual(
            'Some URL: %s' % reverse_lazy('some-login-page'),
            'Some URL: /login/'
        )
        if six.PY2:
            self.assertEqual(
                b'Some URL: %s' % reverse_lazy('some-login-page'),
                'Some URL: /login/'
            )


class ReverseLazySettingsTest(AdminScriptTestCase):
    """
    Test that reverse_lazy can be used in settings without causing a circular
    import error.
    """
    def setUp(self):
        self.write_settings('settings.py', extra="""
from django.core.urlresolvers import reverse_lazy
LOGIN_URL = reverse_lazy('login')""")

    def tearDown(self):
        self.remove_settings('settings.py')

    def test_lazy_in_settings(self):
        out, err = self.run_manage(['validate'])
        self.assertNoOutput(err)


@override_settings(ROOT_URLCONF='urlpatterns_reverse.urls')
class ReverseShortcutTests(TestCase):

    def test_redirect_to_object(self):
        # We don't really need a model; just something with a get_absolute_url
        class FakeObj(object):
            def get_absolute_url(self):
                return "/hi-there/"

        res = redirect(FakeObj())
        self.assertIsInstance(res, HttpResponseRedirect)
        self.assertEqual(res.url, '/hi-there/')

        res = redirect(FakeObj(), permanent=True)
        self.assertIsInstance(res, HttpResponsePermanentRedirect)
        self.assertEqual(res.url, '/hi-there/')

    def test_redirect_to_view_name(self):
        res = redirect('hardcoded2')
        self.assertEqual(res.url, '/hardcoded/doc.pdf')
        res = redirect('places', 1)
        self.assertEqual(res.url, '/places/1/')
        res = redirect('headlines', year='2008', month='02', day='17')
        self.assertEqual(res.url, '/headlines/2008.02.17/')
        self.assertRaises(NoReverseMatch, redirect, 'not-a-view')

    def test_redirect_to_url(self):
        res = redirect('/foo/')
        self.assertEqual(res.url, '/foo/')
        res = redirect('http://example.com/')
        self.assertEqual(res.url, 'http://example.com/')
        # Assert that we can redirect using UTF-8 strings
        res = redirect('/æøå/abc/')
        self.assertEqual(res.url, '/%C3%A6%C3%B8%C3%A5/abc/')
        # Assert that no imports are attempted when dealing with a relative path
        # (previously, the below would resolve in a UnicodeEncodeError from __import__ )
        res = redirect('/æøå.abc/')
        self.assertEqual(res.url, '/%C3%A6%C3%B8%C3%A5.abc/')
        res = redirect('os.path')
        self.assertEqual(res.url, 'os.path')

    def test_no_illegal_imports(self):
        # modules that are not listed in urlpatterns should not be importable
        redirect("urlpatterns_reverse.nonimported_module.view")
        self.assertNotIn("urlpatterns_reverse.nonimported_module", sys.modules)

    @ignore_warnings(category=RemovedInDjango110Warning)
    def test_reverse_by_path_nested(self):
        # Views that are added to urlpatterns using include() should be
        # reversible by dotted path.
        self.assertEqual(reverse('urlpatterns_reverse.views.nested_view'), '/includes/nested_path/')

    def test_redirect_view_object(self):
        from .views import absolute_kwargs_view
        res = redirect(absolute_kwargs_view)
        self.assertEqual(res.url, '/absolute_arg_view/')
        self.assertRaises(NoReverseMatch, redirect, absolute_kwargs_view, wrong_argument=None)


@override_settings(ROOT_URLCONF='urlpatterns_reverse.namespace_urls')
class NamespaceTests(TestCase):

    def test_ambiguous_object(self):
        "Names deployed via dynamic URL objects that require namespaces can't be resolved"
        self.assertRaises(NoReverseMatch, reverse, 'urlobject-view')
        self.assertRaises(NoReverseMatch, reverse, 'urlobject-view', args=[37, 42])
        self.assertRaises(NoReverseMatch, reverse, 'urlobject-view', kwargs={'arg1': 42, 'arg2': 37})

    def test_ambiguous_urlpattern(self):
        "Names deployed via dynamic URL objects that require namespaces can't be resolved"
        self.assertRaises(NoReverseMatch, reverse, 'inner-nothing')
        self.assertRaises(NoReverseMatch, reverse, 'inner-nothing', args=[37, 42])
        self.assertRaises(NoReverseMatch, reverse, 'inner-nothing', kwargs={'arg1': 42, 'arg2': 37})

    def test_non_existent_namespace(self):
        "Non-existent namespaces raise errors"
        self.assertRaises(NoReverseMatch, reverse, 'blahblah:urlobject-view')
        self.assertRaises(NoReverseMatch, reverse, 'test-ns1:blahblah:urlobject-view')

    def test_normal_name(self):
        "Normal lookups work as expected"
        self.assertEqual('/normal/', reverse('normal-view'))
        self.assertEqual('/normal/37/42/', reverse('normal-view', args=[37, 42]))
        self.assertEqual('/normal/42/37/', reverse('normal-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/+%5C$*/', reverse('special-view'))

    def test_simple_included_name(self):
        "Normal lookups work on names included from other patterns"
        self.assertEqual('/included/normal/', reverse('inc-normal-view'))
        self.assertEqual('/included/normal/37/42/', reverse('inc-normal-view', args=[37, 42]))
        self.assertEqual('/included/normal/42/37/', reverse('inc-normal-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/included/+%5C$*/', reverse('inc-special-view'))

    def test_namespace_object(self):
        "Dynamic URL objects can be found using a namespace"
        self.assertEqual('/test1/inner/', reverse('test-ns1:urlobject-view'))
        self.assertEqual('/test1/inner/37/42/', reverse('test-ns1:urlobject-view', args=[37, 42]))
        self.assertEqual('/test1/inner/42/37/', reverse('test-ns1:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/test1/inner/+%5C$*/', reverse('test-ns1:urlobject-special-view'))

    def test_embedded_namespace_object(self):
        "Namespaces can be installed anywhere in the URL pattern tree"
        self.assertEqual('/included/test3/inner/', reverse('test-ns3:urlobject-view'))
        self.assertEqual('/included/test3/inner/37/42/', reverse('test-ns3:urlobject-view', args=[37, 42]))
        self.assertEqual('/included/test3/inner/42/37/', reverse('test-ns3:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/included/test3/inner/+%5C$*/', reverse('test-ns3:urlobject-special-view'))

    def test_namespace_pattern(self):
        "Namespaces can be applied to include()'d urlpatterns"
        self.assertEqual('/ns-included1/normal/', reverse('inc-ns1:inc-normal-view'))
        self.assertEqual('/ns-included1/normal/37/42/', reverse('inc-ns1:inc-normal-view', args=[37, 42]))
        self.assertEqual('/ns-included1/normal/42/37/', reverse('inc-ns1:inc-normal-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/ns-included1/+%5C$*/', reverse('inc-ns1:inc-special-view'))

    def test_namespace_pattern_with_variable_prefix(self):
        "When using an include with namespaces when there is a regex variable in front of it"
        self.assertEqual('/ns-outer/42/normal/', reverse('inc-outer:inc-normal-view', kwargs={'outer': 42}))
        self.assertEqual('/ns-outer/42/normal/', reverse('inc-outer:inc-normal-view', args=[42]))
        self.assertEqual('/ns-outer/42/normal/37/4/', reverse('inc-outer:inc-normal-view', kwargs={'outer': 42, 'arg1': 37, 'arg2': 4}))
        self.assertEqual('/ns-outer/42/normal/37/4/', reverse('inc-outer:inc-normal-view', args=[42, 37, 4]))
        self.assertEqual('/ns-outer/42/+%5C$*/', reverse('inc-outer:inc-special-view', kwargs={'outer': 42}))
        self.assertEqual('/ns-outer/42/+%5C$*/', reverse('inc-outer:inc-special-view', args=[42]))

    def test_multiple_namespace_pattern(self):
        "Namespaces can be embedded"
        self.assertEqual('/ns-included1/test3/inner/', reverse('inc-ns1:test-ns3:urlobject-view'))
        self.assertEqual('/ns-included1/test3/inner/37/42/', reverse('inc-ns1:test-ns3:urlobject-view', args=[37, 42]))
        self.assertEqual('/ns-included1/test3/inner/42/37/', reverse('inc-ns1:test-ns3:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/ns-included1/test3/inner/+%5C$*/', reverse('inc-ns1:test-ns3:urlobject-special-view'))

    def test_nested_namespace_pattern(self):
        "Namespaces can be nested"
        self.assertEqual('/ns-included1/ns-included4/ns-included1/test3/inner/', reverse('inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-view'))
        self.assertEqual('/ns-included1/ns-included4/ns-included1/test3/inner/37/42/', reverse('inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-view', args=[37, 42]))
        self.assertEqual('/ns-included1/ns-included4/ns-included1/test3/inner/42/37/', reverse('inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/ns-included1/ns-included4/ns-included1/test3/inner/+%5C$*/', reverse('inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-special-view'))

    def test_app_lookup_object(self):
        "A default application namespace can be used for lookup"
        self.assertEqual('/default/inner/', reverse('testapp:urlobject-view'))
        self.assertEqual('/default/inner/37/42/', reverse('testapp:urlobject-view', args=[37, 42]))
        self.assertEqual('/default/inner/42/37/', reverse('testapp:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/default/inner/+%5C$*/', reverse('testapp:urlobject-special-view'))

    def test_app_lookup_object_with_default(self):
        "A default application namespace is sensitive to the 'current' app can be used for lookup"
        self.assertEqual('/included/test3/inner/', reverse('testapp:urlobject-view', current_app='test-ns3'))
        self.assertEqual('/included/test3/inner/37/42/', reverse('testapp:urlobject-view', args=[37, 42], current_app='test-ns3'))
        self.assertEqual('/included/test3/inner/42/37/', reverse('testapp:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}, current_app='test-ns3'))
        self.assertEqual('/included/test3/inner/+%5C$*/', reverse('testapp:urlobject-special-view', current_app='test-ns3'))

    def test_app_lookup_object_without_default(self):
        "An application namespace without a default is sensitive to the 'current' app can be used for lookup"
        self.assertEqual('/other2/inner/', reverse('nodefault:urlobject-view'))
        self.assertEqual('/other2/inner/37/42/', reverse('nodefault:urlobject-view', args=[37, 42]))
        self.assertEqual('/other2/inner/42/37/', reverse('nodefault:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/other2/inner/+%5C$*/', reverse('nodefault:urlobject-special-view'))

        self.assertEqual('/other1/inner/', reverse('nodefault:urlobject-view', current_app='other-ns1'))
        self.assertEqual('/other1/inner/37/42/', reverse('nodefault:urlobject-view', args=[37, 42], current_app='other-ns1'))
        self.assertEqual('/other1/inner/42/37/', reverse('nodefault:urlobject-view', kwargs={'arg1': 42, 'arg2': 37}, current_app='other-ns1'))
        self.assertEqual('/other1/inner/+%5C$*/', reverse('nodefault:urlobject-special-view', current_app='other-ns1'))

    def test_special_chars_namespace(self):
        self.assertEqual('/+%5C$*/included/normal/', reverse('special:inc-normal-view'))
        self.assertEqual('/+%5C$*/included/normal/37/42/', reverse('special:inc-normal-view', args=[37, 42]))
        self.assertEqual('/+%5C$*/included/normal/42/37/', reverse('special:inc-normal-view', kwargs={'arg1': 42, 'arg2': 37}))
        self.assertEqual('/+%5C$*/included/+%5C$*/', reverse('special:inc-special-view'))

    def test_namespaces_with_variables(self):
        "Namespace prefixes can capture variables: see #15900"
        self.assertEqual('/inc70/', reverse('inc-ns5:inner-nothing', kwargs={'outer': '70'}))
        self.assertEqual('/inc78/extra/foobar/', reverse('inc-ns5:inner-extra', kwargs={'outer': '78', 'extra': 'foobar'}))
        self.assertEqual('/inc70/', reverse('inc-ns5:inner-nothing', args=['70']))
        self.assertEqual('/inc78/extra/foobar/', reverse('inc-ns5:inner-extra', args=['78', 'foobar']))


@override_settings(ROOT_URLCONF=urlconf_outer.__name__)
class RequestURLconfTests(TestCase):
    def test_urlconf(self):
        response = self.client.get('/test/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'outer:/test/me/,'
                                           b'inner:/inner_urlconf/second_test/')
        response = self.client.get('/inner_urlconf/second_test/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/second_test/')
        self.assertEqual(response.status_code, 404)

    @override_settings(
        MIDDLEWARE_CLASSES=(
            '%s.ChangeURLconfMiddleware' % middleware.__name__,
        )
    )
    def test_urlconf_overridden(self):
        response = self.client.get('/test/me/')
        self.assertEqual(response.status_code, 404)
        response = self.client.get('/inner_urlconf/second_test/')
        self.assertEqual(response.status_code, 404)
        response = self.client.get('/second_test/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'outer:,inner:/second_test/')

    @override_settings(
        MIDDLEWARE_CLASSES=(
            '%s.NullChangeURLconfMiddleware' % middleware.__name__,
        )
    )
    def test_urlconf_overridden_with_null(self):
        self.assertRaises(ImproperlyConfigured, self.client.get, '/test/me/')

    @override_settings(
        MIDDLEWARE_CLASSES=(
            '%s.ChangeURLconfMiddleware' % middleware.__name__,
            '%s.ReverseInnerInResponseMiddleware' % middleware.__name__,
        )
    )
    def test_reverse_inner_in_response_middleware(self):
        """
        Test reversing an URL from the *overridden* URLconf from inside
        a response middleware.
        """
        response = self.client.get('/second_test/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'/second_test/')

    @override_settings(
        MIDDLEWARE_CLASSES=(
            '%s.ChangeURLconfMiddleware' % middleware.__name__,
            '%s.ReverseOuterInResponseMiddleware' % middleware.__name__,
        )
    )
    def test_reverse_outer_in_response_middleware(self):
        """
        Test reversing an URL from the *default* URLconf from inside
        a response middleware.
        """
        message = "Reverse for 'outer' with arguments '()' and keyword arguments '{}' not found."
        with self.assertRaisesMessage(NoReverseMatch, message):
            self.client.get('/second_test/')

    @override_settings(
        MIDDLEWARE_CLASSES=(
            '%s.ChangeURLconfMiddleware' % middleware.__name__,
            '%s.ReverseInnerInStreaming' % middleware.__name__,
        )
    )
    def test_reverse_inner_in_streaming(self):
        """
        Test reversing an URL from the *overridden* URLconf from inside
        a streaming response.
        """
        response = self.client.get('/second_test/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response), b'/second_test/')

    @override_settings(
        MIDDLEWARE_CLASSES=(
            '%s.ChangeURLconfMiddleware' % middleware.__name__,
            '%s.ReverseOuterInStreaming' % middleware.__name__,
        )
    )
    def test_reverse_outer_in_streaming(self):
        """
        Test reversing an URL from the *default* URLconf from inside
        a streaming response.
        """
        message = "Reverse for 'outer' with arguments '()' and keyword arguments '{}' not found."
        with self.assertRaisesMessage(NoReverseMatch, message):
            self.client.get('/second_test/')
            b''.join(self.client.get('/second_test/'))


class ErrorHandlerResolutionTests(TestCase):
    """Tests for handler400, handler404 and handler500"""

    def setUp(self):
        urlconf = 'urlpatterns_reverse.urls_error_handlers'
        urlconf_callables = 'urlpatterns_reverse.urls_error_handlers_callables'
        self.resolver = RegexURLResolver(r'^$', urlconf)
        self.callable_resolver = RegexURLResolver(r'^$', urlconf_callables)

    def test_named_handlers(self):
        handler = (empty_view, {})
        self.assertEqual(self.resolver.resolve_error_handler(400), handler)
        self.assertEqual(self.resolver.resolve_error_handler(404), handler)
        self.assertEqual(self.resolver.resolve_error_handler(500), handler)

    def test_callable_handlers(self):
        handler = (empty_view, {})
        self.assertEqual(self.callable_resolver.resolve_error_handler(400), handler)
        self.assertEqual(self.callable_resolver.resolve_error_handler(404), handler)
        self.assertEqual(self.callable_resolver.resolve_error_handler(500), handler)


@override_settings(ROOT_URLCONF='urlpatterns_reverse.urls_without_full_import')
class DefaultErrorHandlerTests(TestCase):

    def test_default_handler(self):
        "If the urls.py doesn't specify handlers, the defaults are used"
        try:
            response = self.client.get('/test/')
            self.assertEqual(response.status_code, 404)
        except AttributeError:
            self.fail("Shouldn't get an AttributeError due to undefined 404 handler")

        try:
            self.assertRaises(ValueError, self.client.get, '/bad_view/')
        except AttributeError:
            self.fail("Shouldn't get an AttributeError due to undefined 500 handler")


@override_settings(ROOT_URLCONF=None)
class NoRootUrlConfTests(TestCase):
    """Tests for handler404 and handler500 if urlconf is None"""

    def test_no_handler_exception(self):
        self.assertRaises(ImproperlyConfigured, self.client.get, '/test/me/')


@override_settings(ROOT_URLCONF='urlpatterns_reverse.namespace_urls')
class ResolverMatchTests(TestCase):

    def test_urlpattern_resolve(self):
        for path, url_name, app_name, namespace, view_name, func, args, kwargs in resolve_test_data:
            # Test legacy support for extracting "function, args, kwargs"
            match_func, match_args, match_kwargs = resolve(path)
            self.assertEqual(match_func, func)
            self.assertEqual(match_args, args)
            self.assertEqual(match_kwargs, kwargs)

            # Test ResolverMatch capabilities.
            match = resolve(path)
            self.assertEqual(match.__class__, ResolverMatch)
            self.assertEqual(match.url_name, url_name)
            self.assertEqual(match.app_name, app_name)
            self.assertEqual(match.namespace, namespace)
            self.assertEqual(match.view_name, view_name)
            self.assertEqual(match.func, func)
            self.assertEqual(match.args, args)
            self.assertEqual(match.kwargs, kwargs)

            # ... and for legacy purposes:
            self.assertEqual(match[0], func)
            self.assertEqual(match[1], args)
            self.assertEqual(match[2], kwargs)

    def test_resolver_match_on_request(self):
        response = self.client.get('/resolver_match/')
        resolver_match = response.resolver_match
        self.assertEqual(resolver_match.url_name, 'test-resolver-match')

    def test_resolver_match_on_request_before_resolution(self):
        request = HttpRequest()
        self.assertIsNone(request.resolver_match)


@override_settings(ROOT_URLCONF='urlpatterns_reverse.erroneous_urls')
class ErroneousViewTests(TestCase):

    def test_erroneous_resolve(self):
        self.assertRaises(ImportError, self.client.get, '/erroneous_inner/')
        self.assertRaises(ImportError, self.client.get, '/erroneous_outer/')
        self.assertRaises(ViewDoesNotExist, self.client.get, '/missing_inner/')
        self.assertRaises(ViewDoesNotExist, self.client.get, '/missing_outer/')
        self.assertRaises(ViewDoesNotExist, self.client.get, '/uncallable/')

        # Regression test for #21157
        self.assertRaises(ImportError, self.client.get, '/erroneous_unqualified/')

    def test_erroneous_reverse(self):
        """
        Ensure that a useful exception is raised when a regex is invalid in the
        URLConf.
        Refs #6170.
        """
        # The regex error will be hit before NoReverseMatch can be raised
        self.assertRaises(ImproperlyConfigured, reverse, 'whatever blah blah')


class ViewLoadingTests(TestCase):
    def test_view_loading(self):
        self.assertEqual(get_callable('urlpatterns_reverse.views.empty_view'),
                         empty_view)

        # passing a callable should return the callable
        self.assertEqual(get_callable(empty_view), empty_view)

    def test_exceptions(self):
        # A missing view (identified by an AttributeError) should raise
        # ViewDoesNotExist, ...
        six.assertRaisesRegex(self, ViewDoesNotExist,
                              ".*View does not exist in.*",
                              get_callable,
                              'urlpatterns_reverse.views.i_should_not_exist')
        # ... but if the AttributeError is caused by something else don't
        # swallow it.
        self.assertRaises(AttributeError, get_callable,
                          'urlpatterns_reverse.views_broken.i_am_broken')


class IncludeTests(SimpleTestCase):
    def test_include_app_name_but_no_namespace(self):
        msg = "Must specify a namespace if specifying app_name."
        with self.assertRaisesMessage(ValueError, msg):
            include('urls', app_name='bar')
