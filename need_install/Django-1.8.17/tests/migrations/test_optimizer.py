# -*- coding: utf-8 -*-

from django.db import migrations, models
from django.db.migrations.optimizer import MigrationOptimizer
from django.test import TestCase

from .models import CustomModelBase, EmptyManager


class OptimizerTests(TestCase):
    """
    Tests the migration autodetector.
    """

    def optimize(self, operations):
        """
        Handy shortcut for getting results + number of loops
        """
        optimizer = MigrationOptimizer()
        return optimizer.optimize(operations), optimizer._iterations

    def assertOptimizesTo(self, operations, expected, exact=None, less_than=None):
        result, iterations = self.optimize(operations)
        result = [repr(f.deconstruct()) for f in result]
        expected = [repr(f.deconstruct()) for f in expected]
        self.assertEqual(expected, result)
        if exact is not None and iterations != exact:
            raise self.failureException("Optimization did not take exactly %s iterations (it took %s)" % (exact, iterations))
        if less_than is not None and iterations >= less_than:
            raise self.failureException("Optimization did not take less than %s iterations (it took %s)" % (less_than, iterations))

    def test_single(self):
        """
        Tests that the optimizer does nothing on a single operation,
        and that it does it in just one pass.
        """
        self.assertOptimizesTo(
            [migrations.DeleteModel("Foo")],
            [migrations.DeleteModel("Foo")],
            exact=1,
        )

    def test_create_delete_model(self):
        """
        CreateModel and DeleteModel should collapse into nothing.
        """
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.DeleteModel("Foo"),
            ],
            [],
        )

    def test_create_rename_model(self):
        """
        CreateModel should absorb RenameModels.
        """
        managers = [('objects', EmptyManager())]
        self.assertOptimizesTo(
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[("name", models.CharField(max_length=255))],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
                migrations.RenameModel("Foo", "Bar"),
            ],
            [
                migrations.CreateModel(
                    "Bar",
                    [("name", models.CharField(max_length=255))],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                )
            ],
        )

    def test_rename_model_self(self):
        """
        RenameModels should absorb themselves.
        """
        self.assertOptimizesTo(
            [
                migrations.RenameModel("Foo", "Baa"),
                migrations.RenameModel("Baa", "Bar"),
            ],
            [
                migrations.RenameModel("Foo", "Bar"),
            ],
        )

    def test_create_alter_delete_model(self):
        """
        CreateModel, AlterModelTable, AlterUniqueTogether, and DeleteModel should collapse into nothing.
        """
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.AlterModelTable("Foo", "woohoo"),
                migrations.AlterUniqueTogether("Foo", [["a", "b"]]),
                migrations.DeleteModel("Foo"),
            ],
            [],
        )

    def test_optimize_through_create(self):
        """
        We should be able to optimize away create/delete through a create or delete
        of a different model, but only if the create operation does not mention the model
        at all.
        """
        # These should work
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("size", models.IntegerField())]),
                migrations.DeleteModel("Foo"),
            ],
            [
                migrations.CreateModel("Bar", [("size", models.IntegerField())]),
            ],
        )
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("size", models.IntegerField())]),
                migrations.DeleteModel("Bar"),
                migrations.DeleteModel("Foo"),
            ],
            [],
        )
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("size", models.IntegerField())]),
                migrations.DeleteModel("Foo"),
                migrations.DeleteModel("Bar"),
            ],
            [],
        )
        # This should not work - FK should block it
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("other", models.ForeignKey("testapp.Foo"))]),
                migrations.DeleteModel("Foo"),
            ],
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("other", models.ForeignKey("testapp.Foo"))]),
                migrations.DeleteModel("Foo"),
            ],
        )
        # This should not work - bases should block it
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("size", models.IntegerField())], bases=("testapp.Foo", )),
                migrations.DeleteModel("Foo"),
            ],
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("size", models.IntegerField())], bases=("testapp.Foo", )),
                migrations.DeleteModel("Foo"),
            ],
        )

    def test_create_model_add_field(self):
        """
        AddField should optimize into CreateModel.
        """
        managers = [('objects', EmptyManager())]
        self.assertOptimizesTo(
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[("name", models.CharField(max_length=255))],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
                migrations.AddField("Foo", "age", models.IntegerField()),
            ],
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[
                        ("name", models.CharField(max_length=255)),
                        ("age", models.IntegerField()),
                    ],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
            ],
        )

    def test_create_model_add_field_not_through_fk(self):
        """
        AddField should NOT optimize into CreateModel if it's an FK to a model
        that's between them.
        """
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Link", [("url", models.TextField())]),
                migrations.AddField("Foo", "link", models.ForeignKey("migrations.Link")),
            ],
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Link", [("url", models.TextField())]),
                migrations.AddField("Foo", "link", models.ForeignKey("migrations.Link")),
            ],
        )

    def test_create_model_add_field_not_through_m2m_through(self):
        """
        AddField should NOT optimize into CreateModel if it's an M2M using a
        through that's created between them.
        """
        # Note: The middle model is not actually a valid through model,
        # but that doesn't matter, as we never render it.
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("LinkThrough", []),
                migrations.AddField("Foo", "link", models.ManyToManyField("migrations.Link", through="migrations.LinkThrough")),
            ],
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("LinkThrough", []),
                migrations.AddField("Foo", "link", models.ManyToManyField("migrations.Link", through="migrations.LinkThrough")),
            ],
        )

    def test_create_model_alter_field(self):
        """
        AlterField should optimize into CreateModel.
        """
        managers = [('objects', EmptyManager())]
        self.assertOptimizesTo(
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[("name", models.CharField(max_length=255))],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
                migrations.AlterField("Foo", "name", models.IntegerField()),
            ],
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[
                        ("name", models.IntegerField()),
                    ],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
            ],
        )

    def test_create_model_rename_field(self):
        """
        RenameField should optimize into CreateModel.
        """
        managers = [('objects', EmptyManager())]
        self.assertOptimizesTo(
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[("name", models.CharField(max_length=255))],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
                migrations.RenameField("Foo", "name", "title"),
            ],
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[
                        ("title", models.CharField(max_length=255)),
                    ],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
            ],
        )

    def test_add_field_rename_field(self):
        """
        RenameField should optimize into AddField
        """
        self.assertOptimizesTo(
            [
                migrations.AddField("Foo", "name", models.CharField(max_length=255)),
                migrations.RenameField("Foo", "name", "title"),
            ],
            [
                migrations.AddField("Foo", "title", models.CharField(max_length=255)),
            ],
        )

    def test_alter_field_rename_field(self):
        """
        RenameField should optimize to the other side of AlterField,
        and into itself.
        """
        self.assertOptimizesTo(
            [
                migrations.AlterField("Foo", "name", models.CharField(max_length=255)),
                migrations.RenameField("Foo", "name", "title"),
                migrations.RenameField("Foo", "title", "nom"),
            ],
            [
                migrations.RenameField("Foo", "name", "nom"),
                migrations.AlterField("Foo", "nom", models.CharField(max_length=255)),
            ],
        )

    def test_create_model_remove_field(self):
        """
        RemoveField should optimize into CreateModel.
        """
        managers = [('objects', EmptyManager())]
        self.assertOptimizesTo(
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[
                        ("name", models.CharField(max_length=255)),
                        ("age", models.IntegerField()),
                    ],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
                migrations.RemoveField("Foo", "age"),
            ],
            [
                migrations.CreateModel(
                    name="Foo",
                    fields=[
                        ("name", models.CharField(max_length=255)),
                    ],
                    options={'verbose_name': 'Foo'},
                    bases=(CustomModelBase),
                    managers=managers,
                ),
            ],
        )

    def test_add_field_alter_field(self):
        """
        AlterField should optimize into AddField.
        """
        self.assertOptimizesTo(
            [
                migrations.AddField("Foo", "age", models.IntegerField()),
                migrations.AlterField("Foo", "age", models.FloatField(default=2.4)),
            ],
            [
                migrations.AddField("Foo", name="age", field=models.FloatField(default=2.4)),
            ],
        )

    def test_add_field_delete_field(self):
        """
        RemoveField should cancel AddField
        """
        self.assertOptimizesTo(
            [
                migrations.AddField("Foo", "age", models.IntegerField()),
                migrations.RemoveField("Foo", "age"),
            ],
            [],
        )

    def test_alter_field_delete_field(self):
        """
        RemoveField should absorb AlterField
        """
        self.assertOptimizesTo(
            [
                migrations.AlterField("Foo", "age", models.IntegerField()),
                migrations.RemoveField("Foo", "age"),
            ],
            [
                migrations.RemoveField("Foo", "age"),
            ],
        )

    def test_optimize_through_fields(self):
        """
        Checks that field-level through checking is working.
        This should manage to collapse model Foo to nonexistence,
        and model Bar to a single IntegerField called "width".
        """
        self.assertOptimizesTo(
            [
                migrations.CreateModel("Foo", [("name", models.CharField(max_length=255))]),
                migrations.CreateModel("Bar", [("size", models.IntegerField())]),
                migrations.AddField("Foo", "age", models.IntegerField()),
                migrations.AddField("Bar", "width", models.IntegerField()),
                migrations.AlterField("Foo", "age", models.IntegerField()),
                migrations.RenameField("Bar", "size", "dimensions"),
                migrations.RemoveField("Foo", "age"),
                migrations.RenameModel("Foo", "Phou"),
                migrations.RemoveField("Bar", "dimensions"),
                migrations.RenameModel("Phou", "Fou"),
                migrations.DeleteModel("Fou"),
            ],
            [
                migrations.CreateModel("Bar", [("width", models.IntegerField())]),
            ],
        )
