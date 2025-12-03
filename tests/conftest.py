import os
import sys
from pathlib import Path

app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mbm.settings')

if 'DJANGO_SECRET_KEY' not in os.environ:
    os.environ['DJANGO_SECRET_KEY'] = 'test-secret-key-for-pytest-only'

if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'postgres://postgres:postgres@localhost:5432/mbm_test'

os.environ['POSTGRES_REQUIRE_SSL'] = 'False'

def pytest_configure(config):
    import django
    from django.conf import settings

    # Only configure if Django hasn't been configured yet
    if not settings.configured:
        django.setup()
