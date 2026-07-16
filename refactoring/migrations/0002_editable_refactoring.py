from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('refactoring', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='refactoringsuggestion',
            name='developer_edited_code',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='refactoringsuggestion',
            name='was_edited',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='refactoringsuggestion',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='refactoringsuggestion',
            name='accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='refactoringsuggestion',
            name='applied_code',
            field=models.TextField(blank=True, null=True),
        ),
    ]
