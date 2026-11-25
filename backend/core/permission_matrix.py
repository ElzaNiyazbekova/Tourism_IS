"""Human-readable server role matrix. Owner: Amina A."""
ENDPOINTS = {
    "/api/admin/bookings": ["manager", "admin"],
    "/api/admin/stats": ["manager", "admin"],
    "/api/admin/report/export": ["manager", "admin"],
    "/api/analytics/export": ["analyst", "manager", "admin"],
}

def print_permission_matrix(stdout=print):
    stdout("ENDPOINT | roles")
    for endpoint, roles in ENDPOINTS.items():
        stdout(f"{endpoint} | {', '.join(roles)}")
