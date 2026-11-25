"""
Favourite tours: add / remove / list, idempotency, roles, inactive tours.   Owner: Aitore
Run:  python manage.py test catalog.test_favorites
"""
from django.test import TestCase

from catalog.models import Favorite, TourPackage
from core.testing import client_for, make_package, make_user


class FavoriteTests(TestCase):
    def setUp(self):
        self.tourist = make_user("tourist")
        self.c = client_for(self.tourist)
        self.a, self.b = make_package("Tour A"), make_package("Tour B")

    def test_FV1_only_tourists(self):
        for method, url in (("get", "/api/favorites"), ("get", "/api/favorites/ids"), ("put", f"/api/favorites/{self.a.pk}")):
            self.assertEqual(getattr(client_for(), method)(url).status_code, 401, url)
            for role in ("guide", "manager", "admin", "analyst"):
                self.assertEqual(getattr(client_for(make_user(role)), method)(url).status_code, 403, (url, role))

    def test_FV2_add_is_idempotent_and_list_newest_first(self):
        self.assertEqual(self.c.put(f"/api/favorites/{self.a.pk}").status_code, 201)
        self.assertEqual(self.c.put(f"/api/favorites/{self.a.pk}").status_code, 200)   # second click: no duplicate
        self.assertEqual(self.c.put(f"/api/favorites/{self.b.pk}").status_code, 201)
        self.assertEqual(Favorite.objects.filter(user=self.tourist).count(), 2)
        r = self.c.get("/api/favorites")
        self.assertEqual([t["title"] for t in r.data["results"]], ["Tour B", "Tour A"])
        self.assertEqual(self.c.get("/api/favorites/ids").data, sorted([self.a.pk, self.b.pk]))

    def test_FV3_remove_and_unknown_tour(self):
        self.c.put(f"/api/favorites/{self.a.pk}")
        self.assertEqual(self.c.delete(f"/api/favorites/{self.a.pk}").status_code, 204)
        self.assertEqual(self.c.delete(f"/api/favorites/{self.a.pk}").status_code, 204)
        self.assertEqual(self.c.get("/api/favorites/ids").data, [])
        self.assertEqual(self.c.put("/api/favorites/999999").status_code, 404)

    def test_FV4_private_per_tourist_and_inactive_hidden(self):
        self.c.put(f"/api/favorites/{self.a.pk}")
        other = client_for(make_user("tourist"))
        self.assertEqual(other.get("/api/favorites").data["count"], 0)
        TourPackage.objects.filter(pk=self.a.pk).update(is_active=False)
        self.assertEqual(self.c.get("/api/favorites").data["count"], 0)
        self.assertEqual(self.c.get("/api/favorites/ids").data, [])
        self.assertEqual(self.c.put(f"/api/favorites/{self.a.pk}").status_code, 404)
