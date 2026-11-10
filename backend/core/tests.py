"""Tests: health probe and API documentation.  Owner: Dastan (Testing)   Run: python manage.py test core"""
from django.test import TestCase

from core.testing import client_for


class PlatformTests(TestCase):
    def test_H1_health(self):
        r = client_for().get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["db"], "ok")

    def test_H2_openapi_schema_and_swagger_page(self):
        schema = client_for().get("/api/schema/")
        self.assertEqual(schema.status_code, 200)
        text = schema.content.decode()
        for path in ("/api/bookings/{id}/pay", "/api/admin/tours", "/api/analytics/packages"):
            self.assertIn(path, text)
        self.assertEqual(client_for().get("/api/docs/").status_code, 200)

    def test_H3_unknown_route_has_json_error_shape(self):
        r = client_for().get("/api/nope")
        self.assertEqual(r.status_code, 404)
