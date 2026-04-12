# Generated manually for Fusion scholarships / React client document uploads

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarships', '0002_auto_20250201_2228'),
    ]

    operations = [
        migrations.AddField(
            model_name='mcm',
            name='marksheet',
            field=models.FileField(blank=True, null=True, upload_to=''),
        ),
        migrations.AddField(
            model_name='mcm',
            name='fee_receipt',
            field=models.FileField(blank=True, null=True, upload_to=''),
        ),
        migrations.AddField(
            model_name='mcm',
            name='bank_details',
            field=models.FileField(blank=True, null=True, upload_to=''),
        ),
        migrations.AddField(
            model_name='mcm',
            name='affidavit',
            field=models.FileField(blank=True, null=True, upload_to=''),
        ),
        migrations.AddField(
            model_name='mcm',
            name='aadhar_card',
            field=models.FileField(blank=True, null=True, upload_to=''),
        ),
    ]
