import os
import sys
from pathlib import Path

# Add the app directory to Python path so we can import mbm
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

# Set Django settings module for pytest-django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mbm.settings')

# Set required environment variables for testing if not already set
if 'DJANGO_SECRET_KEY' not in os.environ:
    os.environ['DJANGO_SECRET_KEY'] = 'test-secret-key-for-pytest-only'

# Configure database URL for testing if not set
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'postgres://postgres:postgres@localhost:5432/mbm_test'

# Disable SSL requirement for test database
os.environ['POSTGRES_REQUIRE_SSL'] = 'False'


def pytest_configure(config):
    """
    Initialize Django before pytest starts collecting tests.
    This ensures Django apps are loaded before any test modules are imported.
    """
    import django
    from django.conf import settings
    
    # Only configure if Django hasn't been configured yet
    if not settings.configured:
        django.setup()
