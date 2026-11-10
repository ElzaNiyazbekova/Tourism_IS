// Route guards = convenience only. The REAL protection is server-side (DRF permission classes).
import { inject } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { filter, map, take } from 'rxjs';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  if (auth.isLoggedIn() || auth.hasToken()) return true;
  return inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

/** Role guard: waits until /api/me has answered, then lets only the listed roles in. */
export const roleGuard = (...roles: string[]): CanActivateFn => (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const decide = () => {
    if (!auth.isLoggedIn()) return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
    return roles.includes(auth.role() ?? '') ? true : router.createUrlTree(['/forbidden']);
  };
  if (auth.sessionReady()) return decide();
  return toObservable(auth.sessionReady).pipe(filter(Boolean), take(1), map(decide));
};
