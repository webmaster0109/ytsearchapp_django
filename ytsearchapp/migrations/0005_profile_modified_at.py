# Generated by Django 5.0.1 on 2024-02-24 13:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "ytsearchapp",
            "0004_profile_forgot_password_token_profile_is_verified_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="modified_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
