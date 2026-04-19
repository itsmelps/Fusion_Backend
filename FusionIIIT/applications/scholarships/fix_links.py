import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fusion.settings.production') # Try production first
try:
    django.setup()
except Exception:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'Fusion.settings.common' # Fallback
    django.setup()

from applications.scholarships.models import Mcm, Director_gold, Director_silver, Proficiency_dm
from django.conf import settings

def fix_broken_links():
    media_root = settings.MEDIA_ROOT
    # Existing files on disk
    income_cert_fallback = 'Lecture_22.pdf'
    forms_fallback = 'Lecture_20_and_21.pdf'

    models = [Mcm, Director_gold, Director_silver, Proficiency_dm]
    
    count = 0
    for model in models:
        fields = [f.name for f in model._meta.fields if f.get_internal_type() == 'FileField']
        for obj in model.objects.all():
            changed = False
            for field in fields:
                f = getattr(obj, field)
                if not f:
                    continue
                
                # Check if file exists on disk
                file_path = os.path.join(media_root, f.name)
                if not os.path.exists(file_path):
                    print(f"Broken link found: {model.__name__} ID {obj.id}, field {field}, file {f.name}")
                    
                    # Target specific fixes if possible, or general fallback
                    if 'income' in field:
                        setattr(obj, field, income_cert_fallback)
                    elif 'forms' in field:
                        setattr(obj, field, forms_fallback)
                    else:
                        setattr(obj, field, income_cert_fallback)
                    
                    changed = True
                    count += 1
            
            if changed:
                obj.save()
    
    print(f"Fixed {count} broken links across all models.")

if __name__ == '__main__':
    fix_broken_links()
