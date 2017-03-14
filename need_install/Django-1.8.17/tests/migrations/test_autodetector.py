# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import connection, models
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import MigrationQuestioner
from django.db.migrations.state import ModelState, ProjectState
from django.test import TestCase, mock, override_settings

from .models import FoodManager, FoodQuerySet


class DeconstructableObject(object):
    """
    A custom deconstructable object.
    """

    def deconstruct(self):
        return self.__module__ + '.' + self.__class__.__name__, [], {}


class AutodetectorTests(TestCase):
    """
    Tests the migration autodetector.
    """

    author_empty = ModelState("testapp", "Author", [("id", models.AutoField(primary_key=True))])
    author_name = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
    ])
    author_name_null = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200, null=True)),
    ])
    author_name_longer = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=400)),
    ])
    author_name_renamed = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("names", models.CharField(max_length=200)),
    ])
    author_name_default = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200, default='Ada Lovelace')),
    ])
    author_name_deconstructable_1 = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200, default=DeconstructableObject())),
    ])
    author_name_deconstructable_2 = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200, default=DeconstructableObject())),
    ])
    author_name_deconstructable_3 = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200, default=models.IntegerField())),
    ])
    author_name_deconstructable_4 = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200, default=models.IntegerField())),
    ])
    author_custom_pk = ModelState("testapp", "Author", [("pk_field", models.IntegerField(primary_key=True))])
    author_with_biography_non_blank = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField()),
        ("biography", models.TextField()),
    ])
    author_with_biography_blank = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(blank=True)),
        ("biography", models.TextField(blank=True)),
    ])
    author_with_book = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("book", models.ForeignKey("otherapp.Book")),
    ])
    author_with_book_order_wrt = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("book", models.ForeignKey("otherapp.Book")),
    ], options={"order_with_respect_to": "book"})
    author_renamed_with_book = ModelState("testapp", "Writer", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("book", models.ForeignKey("otherapp.Book")),
    ])
    author_with_publisher_string = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("publisher_name", models.CharField(max_length=200)),
    ])
    author_with_publisher = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("publisher", models.ForeignKey("testapp.Publisher")),
    ])
    author_with_user = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("user", models.ForeignKey("auth.User")),
    ])
    author_with_custom_user = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=200)),
        ("user", models.ForeignKey("thirdapp.CustomUser")),
    ])
    author_proxy = ModelState("testapp", "AuthorProxy", [], {"proxy": True}, ("testapp.author",))
    author_proxy_options = ModelState("testapp", "AuthorProxy", [], {
        "proxy": True,
        "verbose_name": "Super Author",
    }, ("testapp.author", ))
    author_proxy_notproxy = ModelState("testapp", "AuthorProxy", [], {}, ("testapp.author", ))
    author_proxy_third = ModelState("thirdapp", "AuthorProxy", [], {"proxy": True}, ("testapp.author", ))
    author_proxy_proxy = ModelState("testapp", "AAuthorProxyProxy", [], {"proxy": True}, ("testapp.authorproxy", ))
    author_unmanaged = ModelState("testapp", "AuthorUnmanaged", [], {"managed": False}, ("testapp.author", ))
    author_unmanaged_managed = ModelState("testapp", "AuthorUnmanaged", [], {}, ("testapp.author", ))
    author_unmanaged_default_pk = ModelState("testapp", "Author", [("id", models.AutoField(primary_key=True))])
    author_unmanaged_custom_pk = ModelState("testapp", "Author", [
        ("pk_field", models.IntegerField(primary_key=True)),
    ])
    author_with_m2m = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("publishers", models.ManyToManyField("testapp.Publisher")),
    ])
    author_with_m2m_blank = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("publishers", models.ManyToManyField("testapp.Publisher", blank=True)),
    ])
    author_with_m2m_through = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("publishers", models.ManyToManyField("testapp.Publisher", through="testapp.Contract")),
    ])
    author_with_former_m2m = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
        ("publishers", models.CharField(max_length=100)),
    ])
    author_with_options = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
    ], {
        "permissions": [('can_hire', 'Can hire')],
        "verbose_name": "Authi",
    })
    author_with_db_table_options = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
    ], {"db_table": "author_one"})
    author_with_new_db_table_options = ModelState("testapp", "Author", [
        ("id", models.AutoField(primary_key=True)),
    ], {"db_table": "author_two"})
    author_renamed_with_db_table_options = ModelState("testapp", "NewAuthor", [
        ("id", models.AutoField(primary_key=True)),
    ], {"db_table": "author_one"})
    author_renamed_with_new_db_table_options = ModelState("testapp", "NewAuthor", [
        ("id", models.AutoField(primary_key=True)),
    ], {"db_table": "author_three"})
    contract = ModelState("testapp", "Contract", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Author")),
        ("publisher", models.ForeignKey("testapp.Publisher")),
    ])
    publisher = ModelState("testapp", "Publisher", [
        ("id", models.AutoField(primary_key=True)),
        ("name", models.CharField(max_length=100)),
    ])
    publisher_with_author = ModelState("testapp", "Publisher", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Author")),
        ("name", models.CharField(max_length=100)),
    ])
    publisher_with_aardvark_author = ModelState("testapp", "Publisher", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Aardvark")),
        ("name", models.CharField(max_length=100)),
    ])
    publisher_with_book = ModelState("testapp", "Publisher", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("otherapp.Book")),
        ("name", models.CharField(max_length=100)),
    ])
    other_pony = ModelState("otherapp", "Pony", [
        ("id", models.AutoField(primary_key=True)),
    ])
    other_pony_food = ModelState("otherapp", "Pony", [
        ("id", models.AutoField(primary_key=True)),
    ], managers=[
        ('food_qs', FoodQuerySet.as_manager()),
        ('food_mgr', FoodManager('a', 'b')),
        ('food_mgr_kwargs', FoodManager('x', 'y', 3, 4)),
    ])
    other_stable = ModelState("otherapp", "Stable", [("id", models.AutoField(primary_key=True))])
    third_thing = ModelState("thirdapp", "Thing", [("id", models.AutoField(primary_key=True))])
    book = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Author")),
        ("title", models.CharField(max_length=200)),
    ])
    book_proxy_fk = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("thirdapp.AuthorProxy")),
        ("title", models.CharField(max_length=200)),
    ])
    book_migrations_fk = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("migrations.UnmigratedModel")),
        ("title", models.CharField(max_length=200)),
    ])
    book_with_no_author = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("title", models.CharField(max_length=200)),
    ])
    book_with_author_renamed = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Writer")),
        ("title", models.CharField(max_length=200)),
    ])
    book_with_field_and_author_renamed = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("writer", models.ForeignKey("testapp.Writer")),
        ("title", models.CharField(max_length=200)),
    ])
    book_with_multiple_authors = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("authors", models.ManyToManyField("testapp.Author")),
        ("title", models.CharField(max_length=200)),
    ])
    book_with_multiple_authors_through_attribution = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("authors", models.ManyToManyField("testapp.Author", through="otherapp.Attribution")),
        ("title", models.CharField(max_length=200)),
    ])
    book_foo_together = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Author")),
        ("title", models.CharField(max_length=200)),
    ], {
        "index_together": {("author", "title")},
        "unique_together": {("author", "title")},
    })
    book_foo_together_2 = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Author")),
        ("title", models.CharField(max_length=200)),
    ], {
        "index_together": {("title", "author")},
        "unique_together": {("title", "author")},
    })
    book_foo_together_3 = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("newfield", models.IntegerField()),
        ("author", models.ForeignKey("testapp.Author")),
        ("title", models.CharField(max_length=200)),
    ], {
        "index_together": {("title", "newfield")},
        "unique_together": {("title", "newfield")},
    })
    book_foo_together_4 = ModelState("otherapp", "Book", [
        ("id", models.AutoField(primary_key=True)),
        ("newfield2", models.IntegerField()),
        ("author", models.ForeignKey("testapp.Author")),
        ("title", models.CharField(max_length=200)),
    ], {
        "index_together": {("title", "newfield2")},
        "unique_together": {("title", "newfield2")},
    })
    attribution = ModelState("otherapp", "Attribution", [
        ("id", models.AutoField(primary_key=True)),
        ("author", models.ForeignKey("testapp.Author")),
        ("book", models.ForeignKey("otherapp.Book")),
    ])
    edition = ModelState("thirdapp", "Edition", [
        ("id", models.AutoField(primary_key=True)),
        ("book", models.ForeignKey("otherapp.Book")),
    ])
    custom_user = ModelState("thirdapp", "CustomUser", [
        ("id", models.AutoField(primary_key=True)),
        ("username", models.CharField(max_length=255)),
    ], bases=(AbstractBaseUser, ))
    custom_user_no_inherit = ModelState("thirdapp", "CustomUser", [
        ("id", models.AutoField(primary_key=True)),
        ("username", models.CharField(max_length=255)),
    ])
    aardvark = ModelState("thirdapp", "Aardvark", [("id", models.AutoField(primary_key=True))])
    aardvark_testapp = ModelState("testapp", "Aardvark", [("id", models.AutoField(primary_key=True))])
    aardvark_based_on_author = ModelState("testapp", "Aardvark", [], bases=("testapp.Author", ))
    aardvark_pk_fk_author = ModelState("testapp", "Aardvark", [
        ("id", models.OneToOneField("testapp.Author", primary_key=True)),
    ])
    knight = ModelState("eggs", "Knight", [("id", models.AutoField(primary_key=True))])
    rabbit = ModelState("eggs", "Rabbit", [
        ("id", models.AutoField(primary_key=True)),
        ("knight", models.ForeignKey("eggs.Knight")),
        ("parent", models.ForeignKey("eggs.Rabbit")),
    ], {"unique_together": {("parent", "knight")}})

    def repr_changes(self, changes, include_dependencies=False):
        output = ""
        for app_label, migrations in sorted(changes.items()):
            output += "  %s:\n" % app_label
            for migration in migrations:
                output += "    %s\n" % migration.name
                for operation in migration.operations:
                    output += "      %s\n" % operation
                if include_dependencies:
                    output += "      Dependencies:\n"
                    if migration.dependencies:
                        for dep in migration.dependencies:
                            output += "        %s\n" % (dep,)
                    else:
                        output += "        None\n"
        return output

    def assertNumberMigrations(self, changes, app_label, number):
        if len(changes.get(app_label, [])) != number:
            self.fail("Incorrect number of migrations (%s) for %s (expected %s)\n%s" % (
                len(changes.get(app_label, [])),
                app_label,
                number,
                self.repr_changes(changes),
            ))

    def assertMigrationDependencies(self, changes, app_label, index, dependencies):
        if not changes.get(app_label):
            self.fail("No migrations found for %s\n%s" % (app_label, self.repr_changes(changes)))
        if len(changes[app_label]) < index + 1:
            self.fail("No migration at index %s for %s\n%s" % (index, app_label, self.repr_changes(changes)))
        migration = changes[app_label][index]
        if set(migration.dependencies) != set(dependencies):
            self.fail("Migration dependencies mismatch for %s.%s (expected %s):\n%s" % (
                app_label,
                migration.name,
                dependencies,
                self.repr_changes(changes, include_dependencies=True),
            ))

    def assertOperationTypes(self, changes, app_label, index, types):
        if not changes.get(app_label):
            self.fail("No migrations found for %s\n%s" % (app_label, self.repr_changes(changes)))
        if len(changes[app_label]) < index + 1:
            self.fail("No migration at index %s for %s\n%s" % (index, app_label, self.repr_changes(changes)))
        migration = changes[app_label][index]
        real_types = [operation.__class__.__name__ for operation in migration.operations]
        if types != real_types:
            self.fail("Operation type mismatch for %s.%s (expected %s):\n%s" % (
                app_label,
                migration.name,
                types,
                self.repr_changes(changes),
            ))

    def assertOperationAttributes(self, changes, app_label, index, operation_index, **attrs):
        if not changes.get(app_label):
            self.fail("No migrations found for %s\n%s" % (app_label, self.repr_changes(changes)))
        if len(changes[app_label]) < index + 1:
            self.fail("No migration at index %s for %s\n%s" % (index, app_label, self.repr_changes(changes)))
        migration = changes[app_label][index]
        if len(changes[app_label]) < index + 1:
            self.fail("No operation at index %s for %s.%s\n%s" % (
                operation_index,
                app_label,
                migration.name,
                self.repr_changes(changes),
            ))
        operation = migration.operations[operation_index]
        for attr, value in attrs.items():
            if getattr(operation, attr, None) != value:
                self.fail("Attribute mismatch for %s.%s op #%s, %s (expected %r, got %r):\n%s" % (
                    app_label,
                    migration.name,
                    operation_index,
                    attr,
                    value,
                    getattr(operation, attr, None),
                    self.repr_changes(changes),
                ))

    def assertOperationFieldAttributes(self, changes, app_label, index, operation_index, **attrs):
        if not changes.get(app_label):
            self.fail("No migrations found for %s\n%s" % (app_label, self.repr_changes(changes)))
        if len(changes[app_label]) < index + 1:
            self.fail("No migration at index %s for %s\n%s" % (index, app_label, self.repr_changes(changes)))
        migration = changes[app_label][index]
        if len(changes[app_label]) < index + 1:
            self.fail("No operation at index %s for %s.%s\n%s" % (
                operation_index,
                app_label,
                migration.name,
                self.repr_changes(changes),
            ))
        operation = migration.operations[operation_index]
        if not hasattr(operation, 'field'):
            self.fail("No field attribute for %s.%s op #%s." % (
                app_label,
                migration.name,
                operation_index,
            ))
        field = operation.field
        for attr, value in attrs.items():
            if getattr(field, attr, None) != value:
                self.fail("Field attribute mismatch for %s.%s op #%s, field.%s (expected %r, got %r):\n%s" % (
                    app_label,
                    migration.name,
                    operation_index,
                    attr,
                    value,
                    getattr(field, attr, None),
                    self.repr_changes(changes),
                ))

    def make_project_state(self, model_states):
        "Shortcut to make ProjectStates from lists of predefined models"
        project_state = ProjectState()
        for model_state in model_states:
            project_state.add_model(model_state.clone())
        return project_state

    def test_arrange_for_graph(self):
        """Tests auto-naming of migrations for graph matching."""
        # Make a fake graph
        graph = MigrationGraph()
        graph.add_node(("testapp", "0001_initial"), None)
        graph.add_node(("testapp", "0002_foobar"), None)
        graph.add_node(("otherapp", "0001_initial"), None)
        graph.add_dependency("testapp.0002_foobar", ("testapp", "0002_foobar"), ("testapp", "0001_initial"))
        graph.add_dependency("testapp.0002_foobar", ("testapp", "0002_foobar"), ("otherapp", "0001_initial"))
        # Use project state to make a new migration change set
        before = self.make_project_state([])
        after = self.make_project_state([self.author_empty, self.other_pony, self.other_stable])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Run through arrange_for_graph
        changes = autodetector.arrange_for_graph(changes, graph)
        # Make sure there's a new name, deps match, etc.
        self.assertEqual(changes["testapp"][0].name, "0003_author")
        self.assertEqual(changes["testapp"][0].dependencies, [("testapp", "0002_foobar")])
        self.assertEqual(changes["otherapp"][0].name, "0002_pony_stable")
        self.assertEqual(changes["otherapp"][0].dependencies, [("otherapp", "0001_initial")])

    def test_trim_apps(self):
        """
        Tests that trim does not remove dependencies but does remove unwanted
        apps.
        """
        # Use project state to make a new migration change set
        before = self.make_project_state([])
        after = self.make_project_state([self.author_empty, self.other_pony, self.other_stable, self.third_thing])
        autodetector = MigrationAutodetector(before, after, MigrationQuestioner(defaults={"ask_initial": True}))
        changes = autodetector._detect_changes()
        # Run through arrange_for_graph
        graph = MigrationGraph()
        changes = autodetector.arrange_for_graph(changes, graph)
        changes["testapp"][0].dependencies.append(("otherapp", "0001_initial"))
        changes = autodetector._trim_to_apps(changes, {"testapp"})
        # Make sure there's the right set of migrations
        self.assertEqual(changes["testapp"][0].name, "0001_initial")
        self.assertEqual(changes["otherapp"][0].name, "0001_initial")
        self.assertNotIn("thirdapp", changes)

    def test_custom_migration_name(self):
        """Tests custom naming of migrations for graph matching."""
        # Make a fake graph
        graph = MigrationGraph()
        graph.add_node(("testapp", "0001_initial"), None)
        graph.add_node(("testapp", "0002_foobar"), None)
        graph.add_node(("otherapp", "0001_initial"), None)
        graph.add_dependency("testapp.0002_foobar", ("testapp", "0002_foobar"), ("testapp", "0001_initial"))

        # Use project state to make a new migration change set
        before = self.make_project_state([])
        after = self.make_project_state([self.author_empty, self.other_pony, self.other_stable])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()

        # Run through arrange_for_graph
        migration_name = 'custom_name'
        changes = autodetector.arrange_for_graph(changes, graph, migration_name)

        # Make sure there's a new name, deps match, etc.
        self.assertEqual(changes["testapp"][0].name, "0003_%s" % migration_name)
        self.assertEqual(changes["testapp"][0].dependencies, [("testapp", "0002_foobar")])
        self.assertEqual(changes["otherapp"][0].name, "0002_%s" % migration_name)
        self.assertEqual(changes["otherapp"][0].dependencies, [("otherapp", "0001_initial")])

    def test_new_model(self):
        """Tests autodetection of new models."""
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.other_pony_food])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Pony")
        self.assertEqual([name for name, mgr in changes['otherapp'][0].operations[0].managers],
                         ['food_qs', 'food_mgr', 'food_mgr_kwargs'])

    def test_old_model(self):
        """Tests deletion of old models."""
        # Make state
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["DeleteModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")

    def test_add_field(self):
        """Tests autodetection of new fields."""
        # Make state
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_name])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name")

    def test_remove_field(self):
        """Tests autodetection of removed fields."""
        # Make state
        before = self.make_project_state([self.author_name])
        after = self.make_project_state([self.author_empty])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RemoveField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name")

    def test_alter_field(self):
        """Tests autodetection of new fields."""
        # Make state
        before = self.make_project_state([self.author_name])
        after = self.make_project_state([self.author_name_longer])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name", preserve_default=True)

    def test_alter_field_to_not_null_with_default(self):
        """
        #23609 - Tests autodetection of nullable to non-nullable alterations.
        """
        class CustomQuestioner(MigrationQuestioner):
            def ask_not_null_alteration(self, field_name, model_name):
                raise Exception("Should not have prompted for not null addition")

        # Make state
        before = self.make_project_state([self.author_name_null])
        after = self.make_project_state([self.author_name_default])
        autodetector = MigrationAutodetector(before, after, CustomQuestioner())
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name", preserve_default=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 0, default='Ada Lovelace')

    def test_alter_field_to_not_null_without_default(self):
        """
        #23609 - Tests autodetection of nullable to non-nullable alterations.
        """
        class CustomQuestioner(MigrationQuestioner):
            def ask_not_null_alteration(self, field_name, model_name):
                # Ignore for now, and let me handle existing rows with NULL
                # myself (e.g. adding a RunPython or RunSQL operation in the new
                # migration file before the AlterField operation)
                return models.NOT_PROVIDED

        # Make state
        before = self.make_project_state([self.author_name_null])
        after = self.make_project_state([self.author_name])
        autodetector = MigrationAutodetector(before, after, CustomQuestioner())
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name", preserve_default=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 0, default=models.NOT_PROVIDED)

    def test_alter_field_to_not_null_oneoff_default(self):
        """
        #23609 - Tests autodetection of nullable to non-nullable alterations.
        """
        class CustomQuestioner(MigrationQuestioner):
            def ask_not_null_alteration(self, field_name, model_name):
                # Provide a one-off default now (will be set on all existing rows)
                return 'Some Name'

        # Make state
        before = self.make_project_state([self.author_name_null])
        after = self.make_project_state([self.author_name])
        autodetector = MigrationAutodetector(before, after, CustomQuestioner())
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name", preserve_default=False)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 0, default="Some Name")

    def test_rename_field(self):
        """Tests autodetection of renamed fields."""
        # Make state
        before = self.make_project_state([self.author_name])
        after = self.make_project_state([self.author_name_renamed])
        autodetector = MigrationAutodetector(before, after, MigrationQuestioner({"ask_rename": True}))
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RenameField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, old_name="name", new_name="names")

    def test_rename_model(self):
        """Tests autodetection of renamed models."""
        # Make state
        before = self.make_project_state([self.author_with_book, self.book])
        after = self.make_project_state([self.author_renamed_with_book, self.book_with_author_renamed])
        autodetector = MigrationAutodetector(before, after, MigrationQuestioner({"ask_rename_model": True}))
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RenameModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, old_name="Author", new_name="Writer")
        # Now that RenameModel handles related fields too, there should be
        # no AlterField for the related field.
        self.assertNumberMigrations(changes, 'otherapp', 0)

    def test_rename_model_with_renamed_rel_field(self):
        """
        Tests autodetection of renamed models while simultaneously renaming one
        of the fields that relate to the renamed model.
        """
        # Make state
        before = self.make_project_state([self.author_with_book, self.book])
        after = self.make_project_state([self.author_renamed_with_book, self.book_with_field_and_author_renamed])
        autodetector = MigrationAutodetector(before, after, MigrationQuestioner({
            "ask_rename": True,
            "ask_rename_model": True,
        }))
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RenameModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, old_name="Author", new_name="Writer")
        # Right number/type of migrations for related field rename?
        # Alter is already taken care of.
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["RenameField"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, old_name="author", new_name="writer")

    def test_fk_dependency(self):
        """Tests that having a ForeignKey automatically adds a dependency."""
        # Make state
        # Note that testapp (author) has no dependencies,
        # otherapp (book) depends on testapp (author),
        # thirdapp (edition) depends on otherapp (book)
        before = self.make_project_state([])
        after = self.make_project_state([self.author_name, self.book, self.edition])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertMigrationDependencies(changes, 'testapp', 0, [])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="Book")
        self.assertMigrationDependencies(changes, 'otherapp', 0, [("testapp", "auto_1")])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'thirdapp', 1)
        self.assertOperationTypes(changes, 'thirdapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'thirdapp', 0, 0, name="Edition")
        self.assertMigrationDependencies(changes, 'thirdapp', 0, [("otherapp", "auto_1")])

    def test_proxy_fk_dependency(self):
        """Tests that FK dependencies still work on proxy models."""
        # Make state
        # Note that testapp (author) has no dependencies,
        # otherapp (book) depends on testapp (authorproxy)
        before = self.make_project_state([])
        after = self.make_project_state([self.author_empty, self.author_proxy_third, self.book_proxy_fk])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertMigrationDependencies(changes, 'testapp', 0, [])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="Book")
        self.assertMigrationDependencies(changes, 'otherapp', 0, [("thirdapp", "auto_1")])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'thirdapp', 1)
        self.assertOperationTypes(changes, 'thirdapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'thirdapp', 0, 0, name="AuthorProxy")
        self.assertMigrationDependencies(changes, 'thirdapp', 0, [("testapp", "auto_1")])

    def test_same_app_no_fk_dependency(self):
        """
        Tests that a migration with a FK between two models of the same app
        does not have a dependency to itself.
        """
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.author_with_publisher, self.publisher])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "CreateModel", "AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="publisher")
        self.assertMigrationDependencies(changes, 'testapp', 0, [])

    def test_circular_fk_dependency(self):
        """
        Tests that having a circular ForeignKey dependency automatically
        resolves the situation into 2 migrations on one side and 1 on the other.
        """
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.author_with_book, self.book, self.publisher_with_book])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertMigrationDependencies(changes, 'testapp', 0, [("otherapp", "auto_1")])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 2)
        self.assertOperationTypes(changes, 'otherapp', 0, ["CreateModel"])
        self.assertOperationTypes(changes, 'otherapp', 1, ["AddField"])
        self.assertMigrationDependencies(changes, 'otherapp', 0, [])
        self.assertMigrationDependencies(changes, 'otherapp', 1, [("otherapp", "auto_1"), ("testapp", "auto_1")])

    def test_same_app_circular_fk_dependency(self):
        """
        Tests that a migration with a FK between two models of the same app does
        not have a dependency to itself.
        """
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.author_with_publisher, self.publisher_with_author])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "CreateModel", "AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="publisher")
        self.assertMigrationDependencies(changes, 'testapp', 0, [])

    def test_same_app_circular_fk_dependency_and_unique_together(self):
        """
        #22275 - Tests that a migration with circular FK dependency does not try
        to create unique together constraint before creating all required fields
        first.
        """
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.knight, self.rabbit])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'eggs', 1)
        self.assertOperationTypes(changes, 'eggs', 0, ["CreateModel", "CreateModel", "AlterUniqueTogether"])
        self.assertNotIn("unique_together", changes['eggs'][0].operations[0].options)
        self.assertNotIn("unique_together", changes['eggs'][0].operations[1].options)
        self.assertMigrationDependencies(changes, 'eggs', 0, [])

    def test_alter_db_table_add(self):
        """Tests detection for adding db_table in model's options."""
        # Make state
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_with_db_table_options])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterModelTable"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="author", table="author_one")

    def test_alter_db_table_change(self):
        """Tests detection for changing db_table in model's options'."""
        # Make state
        before = self.make_project_state([self.author_with_db_table_options])
        after = self.make_project_state([self.author_with_new_db_table_options])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterModelTable"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="author", table="author_two")

    def test_alter_db_table_remove(self):
        """Tests detection for removing db_table in model's options."""
        # Make state
        before = self.make_project_state([self.author_with_db_table_options])
        after = self.make_project_state([self.author_empty])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterModelTable"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="author", table=None)

    def test_alter_db_table_no_changes(self):
        """
        Tests that alter_db_table doesn't generate a migration if no changes
        have been made.
        """
        # Make state
        before = self.make_project_state([self.author_with_db_table_options])
        after = self.make_project_state([self.author_with_db_table_options])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number of migrations?
        self.assertEqual(len(changes), 0)

    def test_keep_db_table_with_model_change(self):
        """
        Tests when model changes but db_table stays as-is, autodetector must not
        create more than one operation.
        """
        # Make state
        before = self.make_project_state([self.author_with_db_table_options])
        after = self.make_project_state([self.author_renamed_with_db_table_options])
        autodetector = MigrationAutodetector(
            before, after, MigrationQuestioner({"ask_rename_model": True})
        )
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RenameModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, old_name="Author", new_name="NewAuthor")

    def test_alter_db_table_with_model_change(self):
        """
        Tests when model and db_table changes, autodetector must create two
        operations.
        """
        # Make state
        before = self.make_project_state([self.author_with_db_table_options])
        after = self.make_project_state([self.author_renamed_with_new_db_table_options])
        autodetector = MigrationAutodetector(
            before, after, MigrationQuestioner({"ask_rename_model": True})
        )
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RenameModel", "AlterModelTable"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, old_name="Author", new_name="NewAuthor")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="newauthor", table="author_three")

    def test_empty_foo_together(self):
        """
        #23452 - Empty unique/index_together shouldn't generate a migration.
        """
        # Explicitly testing for not specified, since this is the case after
        # a CreateModel operation w/o any definition on the original model
        model_state_not_specified = ModelState("a", "model", [("id", models.AutoField(primary_key=True))])
        # Explicitly testing for None, since this was the issue in #23452 after
        # a AlterFooTogether operation with e.g. () as value
        model_state_none = ModelState("a", "model", [
            ("id", models.AutoField(primary_key=True))
        ], {
            "index_together": None,
            "unique_together": None,
        })
        # Explicitly testing for the empty set, since we now always have sets.
        # During removal (('col1', 'col2'),) --> () this becomes set([])
        model_state_empty = ModelState("a", "model", [
            ("id", models.AutoField(primary_key=True))
        ], {
            "index_together": set(),
            "unique_together": set(),
        })

        def test(from_state, to_state, msg):
            before = self.make_project_state([from_state])
            after = self.make_project_state([to_state])
            autodetector = MigrationAutodetector(before, after)
            changes = autodetector._detect_changes()
            if len(changes) > 0:
                ops = ', '.join(o.__class__.__name__ for o in changes['a'][0].operations)
                self.fail('Created operation(s) %s from %s' % (ops, msg))

        tests = (
            (model_state_not_specified, model_state_not_specified, '"not specified" to "not specified"'),
            (model_state_not_specified, model_state_none, '"not specified" to "None"'),
            (model_state_not_specified, model_state_empty, '"not specified" to "empty"'),
            (model_state_none, model_state_not_specified, '"None" to "not specified"'),
            (model_state_none, model_state_none, '"None" to "None"'),
            (model_state_none, model_state_empty, '"None" to "empty"'),
            (model_state_empty, model_state_not_specified, '"empty" to "not specified"'),
            (model_state_empty, model_state_none, '"empty" to "None"'),
            (model_state_empty, model_state_empty, '"empty" to "empty"'),
        )

        for t in tests:
            test(*t)

    def test_add_foo_together(self):
        """Tests index/unique_together detection."""
        # Make state
        before = self.make_project_state([self.author_empty, self.book])
        after = self.make_project_state([self.author_empty, self.book_foo_together])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterUniqueTogether", "AlterIndexTogether"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="book", unique_together={("author", "title")})
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", index_together={("author", "title")})

    def test_remove_foo_together(self):
        """Tests index/unique_together detection."""
        before = self.make_project_state([self.author_empty, self.book_foo_together])
        after = self.make_project_state([self.author_empty, self.book])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterUniqueTogether", "AlterIndexTogether"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="book", unique_together=set())
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", index_together=set())

    def test_foo_together_remove_fk(self):
        """Tests unique_together and field removal detection & ordering"""
        # Make state
        before = self.make_project_state([self.author_empty, self.book_foo_together])
        after = self.make_project_state([self.author_empty, self.book_with_no_author])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, [
            "AlterUniqueTogether", "AlterIndexTogether", "RemoveField"
        ])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="book", unique_together=set())
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", index_together=set())
        self.assertOperationAttributes(changes, "otherapp", 0, 2, model_name="book", name="author")

    def test_foo_together_no_changes(self):
        """
        Tests that index/unique_together doesn't generate a migration if no
        changes have been made.
        """
        # Make state
        before = self.make_project_state([self.author_empty, self.book_foo_together])
        after = self.make_project_state([self.author_empty, self.book_foo_together])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number of migrations?
        self.assertEqual(len(changes), 0)

    def test_foo_together_ordering(self):
        """
        Tests that index/unique_together also triggers on ordering changes.
        """
        # Make state
        before = self.make_project_state([self.author_empty, self.book_foo_together])
        after = self.make_project_state([self.author_empty, self.book_foo_together_2])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterUniqueTogether", "AlterIndexTogether"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="book", unique_together={("title", "author")})
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", index_together={("title", "author")})

    def test_add_field_and_foo_together(self):
        """
        Tests that added fields will be created before using them in
        index/unique_together.
        """
        before = self.make_project_state([self.author_empty, self.book])
        after = self.make_project_state([self.author_empty, self.book_foo_together_3])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AddField", "AlterUniqueTogether", "AlterIndexTogether"])
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", unique_together={("title", "newfield")})
        self.assertOperationAttributes(changes, "otherapp", 0, 2, name="book", index_together={("title", "newfield")})

    def test_remove_field_and_foo_together(self):
        """
        Tests that removed fields will be removed after updating
        index/unique_together.
        """
        before = self.make_project_state([self.author_empty, self.book_foo_together_3])
        after = self.make_project_state([self.author_empty, self.book_foo_together])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterUniqueTogether", "AlterIndexTogether", "RemoveField"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="book", unique_together={("author", "title")})
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", index_together={("author", "title")})

    def test_rename_field_and_foo_together(self):
        """
        Tests that removed fields will be removed after updating
        index/unique_together.
        """
        before = self.make_project_state([self.author_empty, self.book_foo_together_3])
        after = self.make_project_state([self.author_empty, self.book_foo_together_4])
        autodetector = MigrationAutodetector(before, after, MigrationQuestioner({"ask_rename": True}))
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["RenameField", "AlterUniqueTogether", "AlterIndexTogether"])
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="book", unique_together={
            ("title", "newfield2")
        })
        self.assertOperationAttributes(changes, "otherapp", 0, 2, name="book", index_together={("title", "newfield2")})

    def test_proxy(self):
        """Tests that the autodetector correctly deals with proxy models."""
        # First, we test adding a proxy model
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_empty, self.author_proxy])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="AuthorProxy", options={"proxy": True})

        # Now, we test turning a proxy model into a non-proxy model
        # It should delete the proxy then make the real one
        before = self.make_project_state([self.author_empty, self.author_proxy])
        after = self.make_project_state([self.author_empty, self.author_proxy_notproxy])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["DeleteModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="AuthorProxy")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="AuthorProxy", options={})

    def test_proxy_custom_pk(self):
        """
        #23415 - The autodetector must correctly deal with custom FK on proxy
        models.
        """
        # First, we test the default pk field name
        before = self.make_project_state([])
        after = self.make_project_state([self.author_empty, self.author_proxy_third, self.book_proxy_fk])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # The field name the FK on the book model points to
        self.assertEqual(changes['otherapp'][0].operations[0].fields[2][1].rel.field_name, 'id')

        # Now, we test the custom pk field name
        before = self.make_project_state([])
        after = self.make_project_state([self.author_custom_pk, self.author_proxy_third, self.book_proxy_fk])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # The field name the FK on the book model points to
        self.assertEqual(changes['otherapp'][0].operations[0].fields[2][1].rel.field_name, 'pk_field')

    def test_unmanaged_create(self):
        """Tests that the autodetector correctly deals with managed models."""
        # First, we test adding an unmanaged model
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_empty, self.author_unmanaged])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0,
            name="AuthorUnmanaged", options={"managed": False})

    def test_unmanaged_to_managed(self):
        # Now, we test turning an unmanaged model into a managed model
        before = self.make_project_state([self.author_empty, self.author_unmanaged])
        after = self.make_project_state([self.author_empty, self.author_unmanaged_managed])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterModelOptions"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0,
            name="authorunmanaged", options={})

    def test_managed_to_unmanaged(self):
        # Now, we turn managed to unmanaged.
        before = self.make_project_state([self.author_empty, self.author_unmanaged_managed])
        after = self.make_project_state([self.author_empty, self.author_unmanaged])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(changes, "testapp", 0, 0,
            name="authorunmanaged", options={"managed": False})

    def test_unmanaged_custom_pk(self):
        """
        #23415 - The autodetector must correctly deal with custom FK on
        unmanaged models.
        """
        # First, we test the default pk field name
        before = self.make_project_state([])
        after = self.make_project_state([self.author_unmanaged_default_pk, self.book])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # The field name the FK on the book model points to
        self.assertEqual(changes['otherapp'][0].operations[0].fields[2][1].rel.field_name, 'id')

        # Now, we test the custom pk field name
        before = self.make_project_state([])
        after = self.make_project_state([self.author_unmanaged_custom_pk, self.book])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # The field name the FK on the book model points to
        self.assertEqual(changes['otherapp'][0].operations[0].fields[2][1].rel.field_name, 'pk_field')

    @override_settings(AUTH_USER_MODEL="thirdapp.CustomUser")
    def test_swappable(self):
        before = self.make_project_state([self.custom_user])
        after = self.make_project_state([self.custom_user, self.author_with_custom_user])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertMigrationDependencies(changes, 'testapp', 0, [("__setting__", "AUTH_USER_MODEL")])

    def test_swappable_changed(self):
        before = self.make_project_state([self.custom_user, self.author_with_user])
        with override_settings(AUTH_USER_MODEL="thirdapp.CustomUser"):
            after = self.make_project_state([self.custom_user, self.author_with_custom_user])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, model_name="author", name='user')
        fk_field = changes['testapp'][0].operations[0].field
        to_model = '%s.%s' % (fk_field.rel.to._meta.app_label, fk_field.rel.to._meta.object_name)
        self.assertEqual(to_model, 'thirdapp.CustomUser')

    def test_add_field_with_default(self):
        """#22030 - Adding a field with a default should work."""
        # Make state
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_name_default])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="name")

    def test_custom_deconstructable(self):
        """
        Two instances which deconstruct to the same value aren't considered a
        change.
        """
        before = self.make_project_state([self.author_name_deconstructable_1])
        after = self.make_project_state([self.author_name_deconstructable_2])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number of migrations?
        self.assertEqual(len(changes), 0)

    def test_deconstruct_field_kwarg(self):
        """Field instances are handled correctly by nested deconstruction."""
        before = self.make_project_state([self.author_name_deconstructable_3])
        after = self.make_project_state([self.author_name_deconstructable_4])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        self.assertEqual(changes, {})

    def test_deconstruct_type(self):
        """
        #22951 -- Uninstanted classes with deconstruct are correctly returned
        by deep_deconstruct during serialization.
        """
        author = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(
                    max_length=200,
                    # IntegerField intentionally not instantiated.
                    default=models.IntegerField,
                ))
            ],
        )
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([author])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel"])

    def test_replace_string_with_foreignkey(self):
        """
        #22300 - Adding an FK in the same "spot" as a deleted CharField should
        work.
        """
        # Make state
        before = self.make_project_state([self.author_with_publisher_string])
        after = self.make_project_state([self.author_with_publisher, self.publisher])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "RemoveField", "AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Publisher")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="publisher_name")
        self.assertOperationAttributes(changes, 'testapp', 0, 2, name="publisher")

    def test_foreign_key_removed_before_target_model(self):
        """
        Removing an FK and the model it targets in the same change must remove
        the FK field before the model to maintain consistency.
        """
        before = self.make_project_state([self.author_with_publisher, self.publisher])
        after = self.make_project_state([self.author_name])  # removes both the model and FK
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["RemoveField", "DeleteModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="publisher")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="Publisher")

    def test_add_many_to_many(self):
        """#22435 - Adding a ManyToManyField should not prompt for a default."""
        class CustomQuestioner(MigrationQuestioner):
            def ask_not_null_addition(self, field_name, model_name):
                raise Exception("Should not have prompted for not null addition")

        before = self.make_project_state([self.author_empty, self.publisher])
        after = self.make_project_state([self.author_with_m2m, self.publisher])
        autodetector = MigrationAutodetector(before, after, CustomQuestioner())
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="publishers")

    def test_alter_many_to_many(self):
        before = self.make_project_state([self.author_with_m2m, self.publisher])
        after = self.make_project_state([self.author_with_m2m_blank, self.publisher])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="publishers")

    def test_create_with_through_model(self):
        """
        Adding a m2m with a through model and the models that use it should be
        ordered correctly.
        """
        before = self.make_project_state([])
        after = self.make_project_state([self.author_with_m2m_through, self.publisher, self.contract])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, [
            "CreateModel", "CreateModel", "CreateModel", "AddField", "AddField"
        ])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="Contract")
        self.assertOperationAttributes(changes, 'testapp', 0, 2, name="Publisher")
        self.assertOperationAttributes(changes, 'testapp', 0, 3, model_name='contract', name='publisher')
        self.assertOperationAttributes(changes, 'testapp', 0, 4, model_name='author', name='publishers')

    def test_many_to_many_removed_before_through_model(self):
        """
        Removing a ManyToManyField and the "through" model in the same change
        must remove the field before the model to maintain consistency.
        """
        before = self.make_project_state([
            self.book_with_multiple_authors_through_attribution, self.author_name, self.attribution
        ])
        # Remove both the through model and ManyToMany
        after = self.make_project_state([self.book_with_no_author, self.author_name])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["RemoveField", "RemoveField", "RemoveField", "DeleteModel"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="author", model_name='attribution')
        self.assertOperationAttributes(changes, 'otherapp', 0, 1, name="book", model_name='attribution')
        self.assertOperationAttributes(changes, 'otherapp', 0, 2, name="authors", model_name='book')
        self.assertOperationAttributes(changes, 'otherapp', 0, 3, name='Attribution')

    def test_many_to_many_removed_before_through_model_2(self):
        """
        Removing a model that contains a ManyToManyField and the "through" model
        in the same change must remove the field before the model to maintain
        consistency.
        """
        before = self.make_project_state([
            self.book_with_multiple_authors_through_attribution, self.author_name, self.attribution
        ])
        # Remove both the through model and ManyToMany
        after = self.make_project_state([self.author_name])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, [
            "RemoveField", "RemoveField", "RemoveField", "DeleteModel", "DeleteModel"
        ])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="author", model_name='attribution')
        self.assertOperationAttributes(changes, 'otherapp', 0, 1, name="book", model_name='attribution')
        self.assertOperationAttributes(changes, 'otherapp', 0, 2, name="authors", model_name='book')
        self.assertOperationAttributes(changes, 'otherapp', 0, 3, name='Attribution')
        self.assertOperationAttributes(changes, 'otherapp', 0, 4, name='Book')

    def test_m2m_w_through_multistep_remove(self):
        """
        A model with a m2m field that specifies a "through" model cannot be
        removed in the same migration as that through model as the schema will
        pass through an inconsistent state. The autodetector should produce two
        migrations to avoid this issue.
        """
        before = self.make_project_state([self.author_with_m2m_through, self.publisher, self.contract])
        after = self.make_project_state([self.publisher])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, [
            "RemoveField", "RemoveField", "RemoveField", "DeleteModel", "DeleteModel"
        ])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="publishers", model_name='author')
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="author", model_name='contract')
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="publisher", model_name='contract')
        self.assertOperationAttributes(changes, "testapp", 0, 3, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 4, name="Contract")

    def test_concrete_field_changed_to_many_to_many(self):
        """
        #23938 - Tests that changing a concrete field into a ManyToManyField
        first removes the concrete field and then adds the m2m field.
        """
        before = self.make_project_state([self.author_with_former_m2m])
        after = self.make_project_state([self.author_with_m2m, self.publisher])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel", "RemoveField", "AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name='Publisher')
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="publishers", model_name='author')
        self.assertOperationAttributes(changes, 'testapp', 0, 2, name="publishers", model_name='author')

    def test_many_to_many_changed_to_concrete_field(self):
        """
        #23938 - Tests that changing a ManyToManyField into a concrete field
        first removes the m2m field and then adds the concrete field.
        """
        before = self.make_project_state([self.author_with_m2m, self.publisher])
        after = self.make_project_state([self.author_with_former_m2m])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RemoveField", "AddField", "DeleteModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="publishers", model_name='author')
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="publishers", model_name='author')
        self.assertOperationAttributes(changes, 'testapp', 0, 2, name='Publisher')
        self.assertOperationFieldAttributes(changes, 'testapp', 0, 1, max_length=100)

    def test_non_circular_foreignkey_dependency_removal(self):
        """
        If two models with a ForeignKey from one to the other are removed at the
        same time, the autodetector should remove them in the correct order.
        """
        before = self.make_project_state([self.author_with_publisher, self.publisher_with_author])
        after = self.make_project_state([])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RemoveField", "RemoveField", "DeleteModel", "DeleteModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="publisher", model_name='author')
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="author", model_name='publisher')
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 3, name="Publisher")

    def test_alter_model_options(self):
        """Changing a model's options should make a change."""
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_with_options])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, options={
            "permissions": [('can_hire', 'Can hire')],
            "verbose_name": "Authi",
        })

        # Changing them back to empty should also make a change
        before = self.make_project_state([self.author_with_options])
        after = self.make_project_state([self.author_empty])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="author", options={})

    def test_alter_model_options_proxy(self):
        """Changing a proxy model's options should also make a change."""
        before = self.make_project_state([self.author_proxy, self.author_empty])
        after = self.make_project_state([self.author_proxy_options, self.author_empty])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="authorproxy", options={
            "verbose_name": "Super Author"
        })

    def test_set_alter_order_with_respect_to(self):
        """Tests that setting order_with_respect_to adds a field."""
        # Make state
        before = self.make_project_state([self.book, self.author_with_book])
        after = self.make_project_state([self.book, self.author_with_book_order_wrt])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterOrderWithRespectTo"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="author", order_with_respect_to="book")

    def test_add_alter_order_with_respect_to(self):
        """
        Tests that setting order_with_respect_to when adding the FK too does
        things in the right order.
        """
        # Make state
        before = self.make_project_state([self.author_name])
        after = self.make_project_state([self.book, self.author_with_book_order_wrt])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField", "AlterOrderWithRespectTo"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, model_name="author", name="book")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="author", order_with_respect_to="book")

    def test_remove_alter_order_with_respect_to(self):
        """
        Tests that removing order_with_respect_to when removing the FK too does
        things in the right order.
        """
        # Make state
        before = self.make_project_state([self.book, self.author_with_book_order_wrt])
        after = self.make_project_state([self.author_name])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AlterOrderWithRespectTo", "RemoveField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="author", order_with_respect_to=None)
        self.assertOperationAttributes(changes, 'testapp', 0, 1, model_name="author", name="book")

    def test_add_model_order_with_respect_to(self):
        """
        Tests that setting order_with_respect_to when adding the whole model
        does things in the right order.
        """
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.book, self.author_with_book_order_wrt])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "AlterOrderWithRespectTo"])
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="author", order_with_respect_to="book")
        self.assertNotIn("_order", [name for name, field in changes['testapp'][0].operations[0].fields])

    def test_alter_model_managers(self):
        """
        Tests that changing the model managers adds a new operation.
        """
        # Make state
        before = self.make_project_state([self.other_pony])
        after = self.make_project_state([self.other_pony_food])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["AlterModelManagers"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="pony")
        self.assertEqual([name for name, mgr in changes['otherapp'][0].operations[0].managers],
                         ['food_qs', 'food_mgr', 'food_mgr_kwargs'])
        self.assertEqual(changes['otherapp'][0].operations[0].managers[1][1].args, ('a', 'b', 1, 2))
        self.assertEqual(changes['otherapp'][0].operations[0].managers[2][1].args, ('x', 'y', 3, 4))

    def test_swappable_first_inheritance(self):
        """Tests that swappable models get their CreateModel first."""
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.custom_user, self.aardvark])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'thirdapp', 1)
        self.assertOperationTypes(changes, 'thirdapp', 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, 'thirdapp', 0, 0, name="CustomUser")
        self.assertOperationAttributes(changes, 'thirdapp', 0, 1, name="Aardvark")

    @override_settings(AUTH_USER_MODEL="thirdapp.CustomUser")
    def test_swappable_first_setting(self):
        """Tests that swappable models get their CreateModel first."""
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.custom_user_no_inherit, self.aardvark])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'thirdapp', 1)
        self.assertOperationTypes(changes, 'thirdapp', 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, 'thirdapp', 0, 0, name="CustomUser")
        self.assertOperationAttributes(changes, 'thirdapp', 0, 1, name="Aardvark")

    def test_bases_first(self):
        """Tests that bases of other models come first."""
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.aardvark_based_on_author, self.author_name])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="Aardvark")

    def test_multiple_bases(self):
        """#23956 - Tests that inheriting models doesn't move *_ptr fields into AddField operations."""
        A = ModelState("app", "A", [("a_id", models.AutoField(primary_key=True))])
        B = ModelState("app", "B", [("b_id", models.AutoField(primary_key=True))])
        C = ModelState("app", "C", [], bases=("app.A", "app.B"))
        D = ModelState("app", "D", [], bases=("app.A", "app.B"))
        E = ModelState("app", "E", [], bases=("app.A", "app.B"))
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([A, B, C, D, E])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, [
            "CreateModel", "CreateModel", "CreateModel", "CreateModel", "CreateModel"
        ])
        self.assertOperationAttributes(changes, "app", 0, 0, name="A")
        self.assertOperationAttributes(changes, "app", 0, 1, name="B")
        self.assertOperationAttributes(changes, "app", 0, 2, name="C")
        self.assertOperationAttributes(changes, "app", 0, 3, name="D")
        self.assertOperationAttributes(changes, "app", 0, 4, name="E")

    def test_proxy_bases_first(self):
        """Tests that bases of proxies come first."""
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.author_empty, self.author_proxy, self.author_proxy_proxy])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="AuthorProxy")
        self.assertOperationAttributes(changes, 'testapp', 0, 2, name="AAuthorProxyProxy")

    def test_pk_fk_included(self):
        """
        Tests that a relation used as the primary key is kept as part of
        CreateModel.
        """
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.aardvark_pk_fk_author, self.author_name])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Author")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="Aardvark")

    def test_first_dependency(self):
        """
        Tests that a dependency to an app with no migrations uses __first__.
        """
        # Load graph
        loader = MigrationLoader(connection)
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.book_migrations_fk])
        after.real_apps = ["migrations"]
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes(graph=loader.graph)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="Book")
        self.assertMigrationDependencies(changes, 'otherapp', 0, [("migrations", "__first__")])

    @override_settings(MIGRATION_MODULES={"migrations": "migrations.test_migrations"})
    def test_last_dependency(self):
        """
        Tests that a dependency to an app with existing migrations uses the
        last migration of that app.
        """
        # Load graph
        loader = MigrationLoader(connection)
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([self.book_migrations_fk])
        after.real_apps = ["migrations"]
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes(graph=loader.graph)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'otherapp', 1)
        self.assertOperationTypes(changes, 'otherapp', 0, ["CreateModel"])
        self.assertOperationAttributes(changes, 'otherapp', 0, 0, name="Book")
        self.assertMigrationDependencies(changes, 'otherapp', 0, [("migrations", "0002_second")])

    def test_alter_fk_before_model_deletion(self):
        """
        Tests that ForeignKeys are altered _before_ the model they used to
        refer to are deleted.
        """
        # Make state
        before = self.make_project_state([self.author_name, self.publisher_with_author])
        after = self.make_project_state([self.aardvark_testapp, self.publisher_with_aardvark_author])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["CreateModel", "AlterField", "DeleteModel"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="Aardvark")
        self.assertOperationAttributes(changes, 'testapp', 0, 1, name="author")
        self.assertOperationAttributes(changes, 'testapp', 0, 2, name="Author")

    def test_fk_dependency_other_app(self):
        """
        #23100 - Tests that ForeignKeys correctly depend on other apps' models.
        """
        # Make state
        before = self.make_project_state([self.author_name, self.book])
        after = self.make_project_state([self.author_with_book, self.book])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0, name="book")
        self.assertMigrationDependencies(changes, 'testapp', 0, [("otherapp", "__first__")])

    def test_circular_dependency_mixed_addcreate(self):
        """
        #23315 - Tests that the dependency resolver knows to put all CreateModel
        before AddField and not become unsolvable.
        """
        address = ModelState("a", "Address", [
            ("id", models.AutoField(primary_key=True)),
            ("country", models.ForeignKey("b.DeliveryCountry")),
        ])
        person = ModelState("a", "Person", [
            ("id", models.AutoField(primary_key=True)),
        ])
        apackage = ModelState("b", "APackage", [
            ("id", models.AutoField(primary_key=True)),
            ("person", models.ForeignKey("a.Person")),
        ])
        country = ModelState("b", "DeliveryCountry", [
            ("id", models.AutoField(primary_key=True)),
        ])
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([address, person, apackage, country])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'a', 2)
        self.assertNumberMigrations(changes, 'b', 1)
        self.assertOperationTypes(changes, 'a', 0, ["CreateModel", "CreateModel"])
        self.assertOperationTypes(changes, 'a', 1, ["AddField"])
        self.assertOperationTypes(changes, 'b', 0, ["CreateModel", "CreateModel"])

    @override_settings(AUTH_USER_MODEL="a.Tenant")
    def test_circular_dependency_swappable(self):
        """
        #23322 - Tests that the dependency resolver knows to explicitly resolve
        swappable models.
        """
        tenant = ModelState("a", "Tenant", [
            ("id", models.AutoField(primary_key=True)),
            ("primary_address", models.ForeignKey("b.Address"))],
            bases=(AbstractBaseUser, )
        )
        address = ModelState("b", "Address", [
            ("id", models.AutoField(primary_key=True)),
            ("tenant", models.ForeignKey(settings.AUTH_USER_MODEL)),
        ])
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([address, tenant])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'a', 2)
        self.assertOperationTypes(changes, 'a', 0, ["CreateModel"])
        self.assertOperationTypes(changes, 'a', 1, ["AddField"])
        self.assertMigrationDependencies(changes, 'a', 0, [])
        self.assertMigrationDependencies(changes, 'a', 1, [('a', 'auto_1'), ('b', 'auto_1')])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'b', 1)
        self.assertOperationTypes(changes, 'b', 0, ["CreateModel"])
        self.assertMigrationDependencies(changes, 'b', 0, [('__setting__', 'AUTH_USER_MODEL')])

    @override_settings(AUTH_USER_MODEL="b.Tenant")
    def test_circular_dependency_swappable2(self):
        """
        #23322 - Tests that the dependency resolver knows to explicitly resolve
        swappable models but with the swappable not being the first migrated
        model.
        """
        address = ModelState("a", "Address", [
            ("id", models.AutoField(primary_key=True)),
            ("tenant", models.ForeignKey(settings.AUTH_USER_MODEL)),
        ])
        tenant = ModelState("b", "Tenant", [
            ("id", models.AutoField(primary_key=True)),
            ("primary_address", models.ForeignKey("a.Address"))],
            bases=(AbstractBaseUser, )
        )
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([address, tenant])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'a', 2)
        self.assertOperationTypes(changes, 'a', 0, ["CreateModel"])
        self.assertOperationTypes(changes, 'a', 1, ["AddField"])
        self.assertMigrationDependencies(changes, 'a', 0, [])
        self.assertMigrationDependencies(changes, 'a', 1, [('__setting__', 'AUTH_USER_MODEL'), ('a', 'auto_1')])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'b', 1)
        self.assertOperationTypes(changes, 'b', 0, ["CreateModel"])
        self.assertMigrationDependencies(changes, 'b', 0, [('a', 'auto_1')])

    @override_settings(AUTH_USER_MODEL="a.Person")
    def test_circular_dependency_swappable_self(self):
        """
        #23322 - Tests that the dependency resolver knows to explicitly resolve
        swappable models.
        """
        person = ModelState("a", "Person", [
            ("id", models.AutoField(primary_key=True)),
            ("parent1", models.ForeignKey(settings.AUTH_USER_MODEL, related_name='children'))
        ])
        # Make state
        before = self.make_project_state([])
        after = self.make_project_state([person])
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, 'a', 1)
        self.assertOperationTypes(changes, 'a', 0, ["CreateModel"])
        self.assertMigrationDependencies(changes, 'a', 0, [])

    def test_add_blank_textfield_and_charfield(self):
        """
        #23405 - Adding a NOT NULL and blank `CharField` or `TextField`
        without default should not prompt for a default.
        """
        class CustomQuestioner(MigrationQuestioner):
            def ask_not_null_addition(self, field_name, model_name):
                raise Exception("Should not have prompted for not null addition")

        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_with_biography_blank])
        autodetector = MigrationAutodetector(before, after, CustomQuestioner())
        changes = autodetector._detect_changes()
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField", "AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0)

    @mock.patch('django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition')
    def test_add_non_blank_textfield_and_charfield(self, mocked_ask_method):
        """
        #23405 - Adding a NOT NULL and non-blank `CharField` or `TextField`
        without default should prompt for a default.
        """
        before = self.make_project_state([self.author_empty])
        after = self.make_project_state([self.author_with_biography_non_blank])
        autodetector = MigrationAutodetector(before, after, MigrationQuestioner())
        changes = autodetector._detect_changes()
        # need to check for questioner call
        self.assertTrue(mocked_ask_method.called)
        self.assertEqual(mocked_ask_method.call_count, 2)
        self.assertNumberMigrations(changes, 'testapp', 1)
        self.assertOperationTypes(changes, 'testapp', 0, ["AddField", "AddField"])
        self.assertOperationAttributes(changes, 'testapp', 0, 0)
