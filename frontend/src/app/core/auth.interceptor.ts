// Adds the JWT to /api calls and silently refreshes it once on a 401.  Owner: Amina A.
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const isApi = req.url.startsWith('/api');
  if (!isApi) return next(req);

  const auth = inject(AuthService);
  const isAuthCall = req.url.startsWith('/api/auth/');     // login/register/refresh: never retried
  const token = auth.accessToken;

  const authed = token && !isAuthCall ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(authed).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status !== 401 || !isApi || isAuthCall) return throwError(() => err);
      if (!auth.refreshToken) {
        if (auth.isLoggedIn()) auth.logout(true);
        return throwError(() => err);
      }
      return auth.refresh().pipe(
        switchMap(newToken => next(req.clone({ setHeaders: { Authorization: `Bearer ${newToken}` } }))),
        catchError(e => { auth.logout(true); return throwError(() => e); }),
      );
    }),
  );
};
