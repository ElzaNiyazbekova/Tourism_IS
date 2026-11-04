// Login state (signals) + token storage.   Owner: Amina A. (JWT flow) / Aitore (screens)
import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, finalize, map, shareReplay, tap } from 'rxjs';
import { LanguageService } from './language.service';
import { User } from './models';

interface AuthResponse { access: string; refresh: string; user: User; }
const ACCESS = 'access_token';
const REFRESH = 'refresh_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private language = inject(LanguageService);

  readonly user = signal<User | null>(null);
  readonly isLoggedIn = computed(() => this.user() !== null);
  readonly role = computed(() => this.user()?.role ?? null);
  private refreshing$: Observable<string> | null = null;

  get accessToken(): string | null { return this.read(ACCESS); }
  get refreshToken(): string | null { return this.read(REFRESH); }
  hasToken(): boolean { return !!this.accessToken || !!this.refreshToken; }

  login(email: string, password: string): Observable<User> {
    return this.http.post<AuthResponse>('/api/auth/login', { email, password }).pipe(tap(r => this.accept(r)), map(r => r.user));
  }

  register(body: { email: string; password: string; full_name: string; phone: string; preferred_language: string }): Observable<User> {
    return this.http.post<AuthResponse>('/api/auth/register', body).pipe(tap(r => this.accept(r)), map(r => r.user));
  }

  updateProfile(patch: Partial<Pick<User, 'full_name' | 'phone' | 'preferred_language'>>): Observable<User> {
    return this.http.patch<User>('/api/me', patch).pipe(tap(u => this.user.set(u)));
  }

  /** On page reload: if a token is stored, load the profile again. */
  restoreSession(): void {
    if (!this.hasToken()) return;
    this.http.get<User>('/api/me').subscribe({
      next: u => { this.user.set(u); },
      error: () => this.clear(),
    });
  }

  /** One refresh at a time, even when several requests fail together. */
  refresh(): Observable<string> {
    if (!this.refreshing$) {
      this.refreshing$ = this.http.post<{ access: string }>('/api/auth/refresh', { refresh: this.refreshToken }).pipe(
        map(r => r.access),
        tap(a => this.write(ACCESS, a)),
        finalize(() => (this.refreshing$ = null)),
        shareReplay(1),
      );
    }
    return this.refreshing$;
  }

  logout(redirect = true): void {
    this.clear();
    if (redirect) this.router.navigate(['/login']);
  }

  private accept(r: AuthResponse): void {
    this.write(ACCESS, r.access);
    this.write(REFRESH, r.refresh);
    this.user.set(r.user);
    this.language.set(r.user.preferred_language);     // the profile language wins after login
  }
  private clear(): void { this.remove(ACCESS); this.remove(REFRESH); this.user.set(null); }

  private read(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } }
  private write(k: string, v: string): void { try { localStorage.setItem(k, v); } catch { /* ignore */ } }
  private remove(k: string): void { try { localStorage.removeItem(k); } catch { /* ignore */ } }
}
