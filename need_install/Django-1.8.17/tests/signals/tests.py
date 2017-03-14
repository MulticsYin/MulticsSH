from __future__ import unicode_literals

from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.test import TestCase
from django.utils import six

from .models import Author, Book, Car, Person


class BaseSignalTest(TestCase):
    def setUp(self):
        # Save up the number of connected signals so that we can check at the
        # end that all the signals we register get properly unregistered (#9989)
        self.pre_signals = (
            len(signals.pre_save.receivers),
            len(signals.post_save.receivers),
            len(signals.pre_delete.receivers),
            len(signals.post_delete.receivers),
        )

    def tearDown(self):
        # Check that all our signals got disconnected properly.
        post_signals = (
            len(signals.pre_save.receivers),
            len(signals.post_save.receivers),
            len(signals.pre_delete.receivers),
            len(signals.post_delete.receivers),
        )
        self.assertEqual(self.pre_signals, post_signals)


class SignalTests(BaseSignalTest):
    def test_model_pre_init_and_post_init(self):
        data = []

        def pre_init_callback(sender, args, **kwargs):
            data.append(kwargs['kwargs'])
        signals.pre_init.connect(pre_init_callback)

        def post_init_callback(sender, instance, **kwargs):
            data.append(instance)
        signals.post_init.connect(post_init_callback)

        p1 = Person(first_name="John", last_name="Doe")
        self.assertEqual(data, [{}, p1])

    def test_save_signals(self):
        data = []

        def pre_save_handler(signal, sender, instance, **kwargs):
            data.append(
                (instance, kwargs.get("raw", False))
            )

        def post_save_handler(signal, sender, instance, **kwargs):
            data.append(
                (instance, kwargs.get("created"), kwargs.get("raw", False))
            )

        signals.pre_save.connect(pre_save_handler, weak=False)
        signals.post_save.connect(post_save_handler, weak=False)
        try:
            p1 = Person.objects.create(first_name="John", last_name="Smith")

            self.assertEqual(data, [
                (p1, False),
                (p1, True, False),
            ])
            data[:] = []

            p1.first_name = "Tom"
            p1.save()
            self.assertEqual(data, [
                (p1, False),
                (p1, False, False),
            ])
            data[:] = []

            # Calling an internal method purely so that we can trigger a "raw" save.
            p1.save_base(raw=True)
            self.assertEqual(data, [
                (p1, True),
                (p1, False, True),
            ])
            data[:] = []

            p2 = Person(first_name="James", last_name="Jones")
            p2.id = 99999
            p2.save()
            self.assertEqual(data, [
                (p2, False),
                (p2, True, False),
            ])
            data[:] = []
            p2.id = 99998
            p2.save()
            self.assertEqual(data, [
                (p2, False),
                (p2, True, False),
            ])
        finally:
            signals.pre_save.disconnect(pre_save_handler)
            signals.post_save.disconnect(post_save_handler)

    def test_delete_signals(self):
        data = []

        def pre_delete_handler(signal, sender, instance, **kwargs):
            data.append(
                (instance, instance.id is None)
            )

        # #8285: signals can be any callable
        class PostDeleteHandler(object):
            def __init__(self, data):
                self.data = data

            def __call__(self, signal, sender, instance, **kwargs):
                self.data.append(
                    (instance, instance.id is None)
                )
        post_delete_handler = PostDeleteHandler(data)

        signals.pre_delete.connect(pre_delete_handler, weak=False)
        signals.post_delete.connect(post_delete_handler, weak=False)
        try:
            p1 = Person.objects.create(first_name="John", last_name="Smith")
            p1.delete()
            self.assertEqual(data, [
                (p1, False),
                (p1, False),
            ])
            data[:] = []

            p2 = Person(first_name="James", last_name="Jones")
            p2.id = 99999
            p2.save()
            p2.id = 99998
            p2.save()
            p2.delete()
            self.assertEqual(data, [
                (p2, False),
                (p2, False)
            ])
            data[:] = []

            self.assertQuerysetEqual(
                Person.objects.all(), [
                    "James Jones",
                ],
                six.text_type
            )
        finally:
            signals.pre_delete.disconnect(pre_delete_handler)
            signals.post_delete.disconnect(post_delete_handler)

    def test_decorators(self):
        data = []

        @receiver(signals.pre_save, weak=False)
        def decorated_handler(signal, sender, instance, **kwargs):
            data.append(instance)

        @receiver(signals.pre_save, sender=Car, weak=False)
        def decorated_handler_with_sender_arg(signal, sender, instance, **kwargs):
            data.append(instance)

        try:
            c1 = Car.objects.create(make="Volkswagen", model="Passat")
            self.assertEqual(data, [c1, c1])
        finally:
            signals.pre_save.disconnect(decorated_handler)
            signals.pre_save.disconnect(decorated_handler_with_sender_arg, sender=Car)

    def test_save_and_delete_signals_with_m2m(self):
        data = []

        def pre_save_handler(signal, sender, instance, **kwargs):
            data.append('pre_save signal, %s' % instance)
            if kwargs.get('raw'):
                data.append('Is raw')

        def post_save_handler(signal, sender, instance, **kwargs):
            data.append('post_save signal, %s' % instance)
            if 'created' in kwargs:
                if kwargs['created']:
                    data.append('Is created')
                else:
                    data.append('Is updated')
            if kwargs.get('raw'):
                data.append('Is raw')

        def pre_delete_handler(signal, sender, instance, **kwargs):
            data.append('pre_delete signal, %s' % instance)
            data.append('instance.id is not None: %s' % (instance.id is not None))

        def post_delete_handler(signal, sender, instance, **kwargs):
            data.append('post_delete signal, %s' % instance)
            data.append('instance.id is not None: %s' % (instance.id is not None))

        signals.pre_save.connect(pre_save_handler, weak=False)
        signals.post_save.connect(post_save_handler, weak=False)
        signals.pre_delete.connect(pre_delete_handler, weak=False)
        signals.post_delete.connect(post_delete_handler, weak=False)
        try:
            a1 = Author.objects.create(name='Neal Stephenson')
            self.assertEqual(data, [
                "pre_save signal, Neal Stephenson",
                "post_save signal, Neal Stephenson",
                "Is created"
            ])
            data[:] = []

            b1 = Book.objects.create(name='Snow Crash')
            self.assertEqual(data, [
                "pre_save signal, Snow Crash",
                "post_save signal, Snow Crash",
                "Is created"
            ])
            data[:] = []

            # Assigning and removing to/from m2m shouldn't generate an m2m signal.
            b1.authors = [a1]
            self.assertEqual(data, [])
            b1.authors = []
            self.assertEqual(data, [])
        finally:
            signals.pre_save.disconnect(pre_save_handler)
            signals.post_save.disconnect(post_save_handler)
            signals.pre_delete.disconnect(pre_delete_handler)
            signals.post_delete.disconnect(post_delete_handler)

    def test_disconnect_in_dispatch(self):
        """
        Test that signals that disconnect when being called don't mess future
        dispatching.
        """

        class Handler(object):
            def __init__(self, param):
                self.param = param
                self._run = False

            def __call__(self, signal, sender, **kwargs):
                self._run = True
                signal.disconnect(receiver=self, sender=sender)

        a, b = Handler(1), Handler(2)
        signals.post_save.connect(a, sender=Person, weak=False)
        signals.post_save.connect(b, sender=Person, weak=False)
        Person.objects.create(first_name='John', last_name='Smith')

        self.assertTrue(a._run)
        self.assertTrue(b._run)
        self.assertEqual(signals.post_save.receivers, [])


class LazyModelRefTest(BaseSignalTest):
    def setUp(self):
        super(LazyModelRefTest, self).setUp()
        self.received = []

    def receiver(self, **kwargs):
        self.received.append(kwargs)

    def test_invalid_sender_model_name(self):
        with self.assertRaisesMessage(ValueError,
                    "Specified sender must either be a model or a "
                    "model name of the 'app_label.ModelName' form."):
            signals.post_init.connect(self.receiver, sender='invalid')

    def test_already_loaded_model(self):
        signals.post_init.connect(
            self.receiver, sender='signals.Book', weak=False
        )
        try:
            instance = Book()
            self.assertEqual(self.received, [{
                'signal': signals.post_init,
                'sender': Book,
                'instance': instance
            }])
        finally:
            signals.post_init.disconnect(self.receiver, sender=Book)

    def test_not_loaded_model(self):
        signals.post_init.connect(
            self.receiver, sender='signals.Created', weak=False
        )

        try:
            class Created(models.Model):
                pass

            instance = Created()
            self.assertEqual(self.received, [{
                'signal': signals.post_init, 'sender': Created, 'instance': instance
            }])
        finally:
            signals.post_init.disconnect(self.receiver, sender=Created)
