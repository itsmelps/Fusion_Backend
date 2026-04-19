import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fusion.settings.development')
django.setup()

from applications.scholarships.models import Mcm, Director_gold, Director_silver, Proficiency_dm
from django.conf import settings

def main():
    media_root = settings.MEDIA_ROOT
    ic_fb = 'Lecture_22.pdf'
    f_fb = 'Lecture_20_and_21.pdf'
    models = [Mcm, Director_gold, Director_silver, Proficiency_dm]
    counts = {m.__name__: 0 for m in models}

    for m in models:
        file_fields = [f.name for f in m._meta.fields if f.get_internal_type() == 'FileField']
        for o in m.objects.all():
            changed = False
            for f_name in file_fields:
                f_val = getattr(o, f_name)
                if f_val:
                    # Check if file exists on disk
                    file_path = os.path.join(media_root, f_val.name)
                    if not os.path.exists(file_path):
                        # Fix it
                        new_val = ic_fb if 'income' in f_name else f_fb
                        setattr(o, f_name, new_val)
                        changed = True
                        counts[m.__name__] += 1
            if changed:
                o.save()
    
    print(f'Fixed broken links: {counts}')

if __name__ == '__main__':
    main()
