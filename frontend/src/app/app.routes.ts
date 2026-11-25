// Lazy-loaded routes.  Owner: Amina A. (guards) / Aitore (screens)
// NOTE: guards only improve UX. The server enforces roles on every endpoint (401/403).
import { Routes } from '@angular/router';
import { authGuard, roleGuard } from './core/guards';

const staff = roleGuard('manager', 'admin');
const adminOnly = roleGuard('admin');
const anyAdmin = roleGuard('manager', 'admin', 'analyst');

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'tours' },
  { path: 'tours', loadComponent: () => import('./features/tours/tour-list.component').then(m => m.TourListComponent) },
  { path: 'tours/:id', loadComponent: () => import('./features/tours/tour-detail.component').then(m => m.TourDetailComponent) },
  { path: 'guides/:id', loadComponent: () => import('./features/guides/guide-profile.component').then(m => m.GuideProfileComponent) },
  { path: 'login', loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./features/auth/register.component').then(m => m.RegisterComponent) },
  { path: 'my-bookings', canActivate: [authGuard], loadComponent: () => import('./features/bookings/my-bookings.component').then(m => m.MyBookingsComponent) },
  { path: 'manage-bookings', canActivate: [roleGuard('tourist')], loadComponent: () => import('./features/flexbook/manage-bookings.component').then(m => m.ManageBookingsComponent) },
  { path: 'favorites', canActivate: [roleGuard('tourist')], loadComponent: () => import('./features/favorites/favorites.component').then(m => m.FavoritesComponent) },
  { path: 'guide', canActivate: [roleGuard('guide')], loadComponent: () => import('./features/guide-cabinet/guide-cabinet.component').then(m => m.GuideCabinetComponent) },
  { path: 'pay/:id', canActivate: [roleGuard('tourist')], loadComponent: () => import('./features/payment/payment.component').then(m => m.PaymentComponent) },
  {
    path: 'admin', canActivate: [anyAdmin],
    loadComponent: () => import('./features/admin/admin-layout.component').then(m => m.AdminLayoutComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', canActivate: [staff], loadComponent: () => import('./features/admin/admin-dashboard.component').then(m => m.AdminDashboardComponent) },
      { path: 'bookings', canActivate: [staff], loadComponent: () => import('./features/admin/admin-bookings.component').then(m => m.AdminBookingsComponent) },
      { path: 'tours', canActivate: [staff], loadComponent: () => import('./features/admin/admin-tours.component').then(m => m.AdminToursComponent) },
      { path: 'tours/new', canActivate: [staff], loadComponent: () => import('./features/admin/admin-tour-form.component').then(m => m.AdminTourFormComponent) },
      { path: 'tours/:id', canActivate: [staff], loadComponent: () => import('./features/admin/admin-tour-form.component').then(m => m.AdminTourFormComponent) },
      { path: 'departures', canActivate: [staff], loadComponent: () => import('./features/admin/admin-departures.component').then(m => m.AdminDeparturesComponent) },
      { path: 'departures/new', canActivate: [staff], loadComponent: () => import('./features/admin/admin-departure-form.component').then(m => m.AdminDepartureFormComponent) },
      { path: 'departures/:id', canActivate: [staff], loadComponent: () => import('./features/admin/admin-departure-form.component').then(m => m.AdminDepartureFormComponent) },
      { path: 'bookings-review', canActivate: [staff], loadComponent: () => import('./features/admin/admin-bookings-review.component').then(m => m.AdminBookingsReviewComponent) },
      { path: 'audit', canActivate: [adminOnly], loadComponent: () => import('./features/admin/admin-audit.component').then(m => m.AdminAuditComponent) },
      { path: 'audit-integrity', canActivate: [adminOnly], loadComponent: () => import('./features/admin/admin-audit-integrity.component').then(m => m.AdminAuditIntegrityComponent) },
      { path: 'reports', loadComponent: () => import('./features/admin/admin-reports.component').then(m => m.AdminReportsComponent) },
    ],
  },
  { path: 'forbidden', loadComponent: () => import('./shared/forbidden.component').then(m => m.ForbiddenComponent) },
  { path: '**', loadComponent: () => import('./shared/not-found.component').then(m => m.NotFoundComponent) },
];
