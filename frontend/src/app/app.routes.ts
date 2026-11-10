// Lazy-loaded routes.  Owner: Amina A. (guards) / Aitore (screens)
// NOTE: guards only improve UX. The server enforces roles on every endpoint (401/403).
import { Routes } from '@angular/router';
import { authGuard, roleGuard } from './core/guards';

const staff = roleGuard('manager', 'admin');
const anyAdmin = roleGuard('manager', 'admin', 'analyst');

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'tours' },
  { path: 'tours', loadComponent: () => import('./features/tours/tour-list.component').then(m => m.TourListComponent) },
  { path: 'tours/:id', loadComponent: () => import('./features/tours/tour-detail.component').then(m => m.TourDetailComponent) },
  { path: 'login', loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./features/auth/register.component').then(m => m.RegisterComponent) },
  { path: 'my-bookings', canActivate: [authGuard], loadComponent: () => import('./features/bookings/my-bookings.component').then(m => m.MyBookingsComponent) },
  { path: 'pay/:id', canActivate: [roleGuard('tourist')], loadComponent: () => import('./features/payment/payment.component').then(m => m.PaymentComponent) },
  {
    path: 'admin', canActivate: [anyAdmin],
    loadComponent: () => import('./features/admin/admin-layout.component').then(m => m.AdminLayoutComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'reports' },
      { path: 'tours', canActivate: [staff], loadComponent: () => import('./features/admin/admin-tours.component').then(m => m.AdminToursComponent) },
      { path: 'tours/new', canActivate: [staff], loadComponent: () => import('./features/admin/admin-tour-form.component').then(m => m.AdminTourFormComponent) },
      { path: 'tours/:id', canActivate: [staff], loadComponent: () => import('./features/admin/admin-tour-form.component').then(m => m.AdminTourFormComponent) },
      { path: 'departures', canActivate: [staff], loadComponent: () => import('./features/admin/admin-departures.component').then(m => m.AdminDeparturesComponent) },
      { path: 'departures/new', canActivate: [staff], loadComponent: () => import('./features/admin/admin-departure-form.component').then(m => m.AdminDepartureFormComponent) },
      { path: 'departures/:id', canActivate: [staff], loadComponent: () => import('./features/admin/admin-departure-form.component').then(m => m.AdminDepartureFormComponent) },
      { path: 'reports', loadComponent: () => import('./features/admin/admin-reports.component').then(m => m.AdminReportsComponent) },
    ],
  },
  { path: 'forbidden', loadComponent: () => import('./shared/forbidden.component').then(m => m.ForbiddenComponent) },
  { path: '**', loadComponent: () => import('./shared/not-found.component').then(m => m.NotFoundComponent) },
];
