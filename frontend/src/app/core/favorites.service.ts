// Tourist's favourite tours: one shared set of ids for every heart on the page.  Owner: Aitore
// API: GET /api/favorites/ids, PUT|DELETE /api/favorites/<id>  (role "tourist" only)
import { HttpClient } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { AuthService } from './auth.service';

@Injectable({ providedIn: 'root' })
export class FavoritesService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  private readonly ids = signal<ReadonlySet<number>>(new Set());
  readonly count = computed(() => this.ids().size);
  /** hearts are shown to tourists and to visitors (who are sent to log in); staff and guides do not get them */
  readonly available = computed(() => !this.auth.isLoggedIn() || this.auth.role() === 'tourist');

  constructor() {
    // (re)load on login, clear on logout / role change
    effect(() => {
      const tourist = this.auth.role() === 'tourist';
      untracked(() => tourist ? this.reload() : this.ids.set(new Set()));
    });
  }

  has(id: number): boolean { return this.ids().has(id); }

  reload(): void {
    this.http.get<number[]>('/api/favorites/ids').subscribe({ next: ids => this.ids.set(new Set(ids)), error: () => {} });
  }

  /** optimistic: the heart changes at once and goes back if the server says no */
  toggle(id: number): void {
    const saved = this.has(id);
    this.set(id, !saved);
    const req = saved ? this.http.delete(`/api/favorites/${id}`) : this.http.put(`/api/favorites/${id}`, null);
    req.subscribe({ error: () => this.set(id, saved) });
  }

  private set(id: number, on: boolean): void {
    const next = new Set(this.ids());
    if (on) next.add(id); else next.delete(id);
    this.ids.set(next);
  }
}
