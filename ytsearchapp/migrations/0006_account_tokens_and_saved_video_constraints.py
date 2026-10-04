import django.db.models.deletion
from django.db import migrations, models


def invalidate_legacy_tokens(apps, schema_editor):
    Profile = apps.get_model('ytsearchapp', 'Profile')
    Profile.objects.update(verification_token=None, forgot_password_token=None)


def normalize_legacy_data(apps, schema_editor):
    Profile = apps.get_model('ytsearchapp', 'Profile')
    SavedVideos = apps.get_model('ytsearchapp', 'SavedVideos')
    Profile.objects.filter(is_verified__isnull=True).update(is_verified=False)
    # Rows without a usable link cannot satisfy the new URL field or be useful
    # to users, so remove only those incomplete legacy records.
    SavedVideos.objects.filter(video_link__isnull=True).delete()
    SavedVideos.objects.filter(video_link='').delete()
    for field in (
        'video_title', 'video_desc', 'video_image', 'video_views',
        'video_published_date', 'video_channel_name',
    ):
        SavedVideos.objects.filter(**{f'{field}__isnull': True}).update(**{field: ''})


class Migration(migrations.Migration):
    dependencies = [
        ('ytsearchapp', '0005_profile_modified_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='password_reset_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='verification_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='forgot_password_token',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.RunPython(normalize_legacy_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='profile',
            name='is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='profile',
            name='verification_token',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_desc',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_image',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_link',
            field=models.URLField(max_length=500),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_published_date',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_title',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_views',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='user_profile',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='saved_videos',
                to='auth.user',
            ),
        ),
        migrations.AlterField(
            model_name='savedvideos',
            name='video_channel_name',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddConstraint(
            model_name='savedvideos',
            constraint=models.UniqueConstraint(
                fields=('user_profile', 'video_link'),
                name='unique_saved_video_per_user',
            ),
        ),
        migrations.RunPython(invalidate_legacy_tokens, migrations.RunPython.noop),
    ]
