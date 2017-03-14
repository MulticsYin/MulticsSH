from django.contrib.auth import get_user_model
from django.contrib.auth.models import (
    AbstractUser, Group, Permission, User, UserManager,
)
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.db.models.signals import post_save
from django.test import TestCase, override_settings


@override_settings(USE_TZ=False)
class NaturalKeysTestCase(TestCase):
    fixtures = ['authtestdata.json']

    def test_user_natural_key(self):
        staff_user = User.objects.get(username='staff')
        self.assertEqual(User.objects.get_by_natural_key('staff'), staff_user)
        self.assertEqual(staff_user.natural_key(), ('staff',))

    def test_group_natural_key(self):
        users_group = Group.objects.create(name='users')
        self.assertEqual(Group.objects.get_by_natural_key('users'), users_group)


@override_settings(USE_TZ=False)
class LoadDataWithoutNaturalKeysTestCase(TestCase):
    fixtures = ['regular.json']

    def test_user_is_created_and_added_to_group(self):
        user = User.objects.get(username='my_username')
        group = Group.objects.get(name='my_group')
        self.assertEqual(group, user.groups.get())


@override_settings(USE_TZ=False)
class LoadDataWithNaturalKeysTestCase(TestCase):
    fixtures = ['natural.json']

    def test_user_is_created_and_added_to_group(self):
        user = User.objects.get(username='my_username')
        group = Group.objects.get(name='my_group')
        self.assertEqual(group, user.groups.get())


class LoadDataWithNaturalKeysAndMultipleDatabasesTestCase(TestCase):
    multi_db = True

    def test_load_data_with_user_permissions(self):
        # Create test contenttypes for both databases
        default_objects = [
            ContentType.objects.db_manager('default').create(
                model='examplemodela',
                app_label='app_a',
            ),
            ContentType.objects.db_manager('default').create(
                model='examplemodelb',
                app_label='app_b',
            ),
        ]
        other_objects = [
            ContentType.objects.db_manager('other').create(
                model='examplemodelb',
                app_label='app_b',
            ),
            ContentType.objects.db_manager('other').create(
                model='examplemodela',
                app_label='app_a',
            ),
        ]

        # Now we create the test UserPermission
        Permission.objects.db_manager("default").create(
            name="Can delete example model b",
            codename="delete_examplemodelb",
            content_type=default_objects[1],
        )
        Permission.objects.db_manager("other").create(
            name="Can delete example model b",
            codename="delete_examplemodelb",
            content_type=other_objects[0],
        )

        perm_default = Permission.objects.get_by_natural_key(
            'delete_examplemodelb',
            'app_b',
            'examplemodelb',
        )

        perm_other = Permission.objects.db_manager('other').get_by_natural_key(
            'delete_examplemodelb',
            'app_b',
            'examplemodelb',
        )

        self.assertEqual(perm_default.content_type_id, default_objects[1].id)
        self.assertEqual(perm_other.content_type_id, other_objects[0].id)


class UserManagerTestCase(TestCase):

    def test_create_user(self):
        email_lowercase = 'normal@normal.com'
        user = User.objects.create_user('user', email_lowercase)
        self.assertEqual(user.email, email_lowercase)
        self.assertEqual(user.username, 'user')
        self.assertFalse(user.has_usable_password())

    def test_create_user_email_domain_normalize_rfc3696(self):
        # According to  http://tools.ietf.org/html/rfc3696#section-3
        # the "@" symbol can be part of the local part of an email address
        returned = UserManager.normalize_email(r'Abc\@DEF@EXAMPLE.com')
        self.assertEqual(returned, r'Abc\@DEF@example.com')

    def test_create_user_email_domain_normalize(self):
        returned = UserManager.normalize_email('normal@DOMAIN.COM')
        self.assertEqual(returned, 'normal@domain.com')

    def test_create_user_email_domain_normalize_with_whitespace(self):
        returned = UserManager.normalize_email('email\ with_whitespace@D.COM')
        self.assertEqual(returned, 'email\ with_whitespace@d.com')

    def test_empty_username(self):
        self.assertRaisesMessage(
            ValueError,
            'The given username must be set',
            User.objects.create_user, username=''
        )


class AbstractUserTestCase(TestCase):
    def test_email_user(self):
        # valid send_mail parameters
        kwargs = {
            "fail_silently": False,
            "auth_user": None,
            "auth_password": None,
            "connection": None,
            "html_message": None,
        }
        abstract_user = AbstractUser(email='foo@bar.com')
        abstract_user.email_user(subject="Subject here",
            message="This is a message", from_email="from@domain.com", **kwargs)
        # Test that one message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # Verify that test email contains the correct attributes:
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Subject here")
        self.assertEqual(message.body, "This is a message")
        self.assertEqual(message.from_email, "from@domain.com")
        self.assertEqual(message.to, [abstract_user.email])

    def test_last_login_default(self):
        user1 = User.objects.create(username='user1')
        self.assertIsNone(user1.last_login)

        user2 = User.objects.create_user(username='user2')
        self.assertIsNone(user2.last_login)


class IsActiveTestCase(TestCase):
    """
    Tests the behavior of the guaranteed is_active attribute
    """

    def test_builtin_user_isactive(self):
        user = User.objects.create(username='foo', email='foo@bar.com')
        # is_active is true by default
        self.assertEqual(user.is_active, True)
        user.is_active = False
        user.save()
        user_fetched = User.objects.get(pk=user.pk)
        # the is_active flag is saved
        self.assertFalse(user_fetched.is_active)

    @override_settings(AUTH_USER_MODEL='auth.IsActiveTestUser1')
    def test_is_active_field_default(self):
        """
        tests that the default value for is_active is provided
        """
        UserModel = get_user_model()
        user = UserModel(username='foo')
        self.assertEqual(user.is_active, True)
        # you can set the attribute - but it will not save
        user.is_active = False
        # there should be no problem saving - but the attribute is not saved
        user.save()
        user_fetched = UserModel._default_manager.get(pk=user.pk)
        # the attribute is always true for newly retrieved instance
        self.assertEqual(user_fetched.is_active, True)


class TestCreateSuperUserSignals(TestCase):
    """
    Simple test case for ticket #20541
    """
    def post_save_listener(self, *args, **kwargs):
        self.signals_count += 1

    def setUp(self):
        self.signals_count = 0
        post_save.connect(self.post_save_listener, sender=User)

    def tearDown(self):
        post_save.disconnect(self.post_save_listener, sender=User)

    def test_create_user(self):
        User.objects.create_user("JohnDoe")
        self.assertEqual(self.signals_count, 1)

    def test_create_superuser(self):
        User.objects.create_superuser("JohnDoe", "mail@example.com", "1")
        self.assertEqual(self.signals_count, 1)
