// Lazy-loaded routes.  Owner: Amina A. (guards) / Aitore (screens)
// NOTE: guards only improve UX. The server enforces roles on every endpoint (401/403).
import { Routes } from '@angular/router';
import { authGuard } from './core/guards';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'tours' },
  { path: 'tours', loadComponent: () => import('./features/tours/tour-list.component').then(m => m.TourListComponent) },
  { path: 'tours/:id', loadComponent: () => import('./features/tours/tour-detail.component').then(m => m.TourDetailComponent) },
  { path: 'login', loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./features/auth/register.component').then(m => m.RegisterComponent) },
  { path: 'my-bookings', canActivate: [authGuard], loadComponent: () => import('./features/bookings/my-bookings.component').then(m => m.MyBookingsComponent) },
  { path: '**', loadComponent: () => import('./shared/not-found.component').then(m => m.NotFoundComponent) },
];
