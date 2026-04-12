from django.test import SimpleTestCase


class ScholarshipsUrlsImportTests(SimpleTestCase):
    def test_urls_module_imports(self):
        from applications.scholarships import urls  # noqa: F401

    def test_api_urls_import(self):
        from applications.scholarships.api import urls as api_urls  # noqa: F401
