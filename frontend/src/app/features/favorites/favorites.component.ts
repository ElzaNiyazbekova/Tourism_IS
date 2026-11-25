// "My favourites": tours the tourist saved with ♡.  Owner: Aitore
// Data: GET /api/favorites?lang=&page=   (role "tourist")
import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { FavoritesApi } from '../../core/api.services';
import { FavoritesService } from '../../core/favorites.service';
import { LanguageService } from '../../core/language.service';
import { Page, Tour } from '../../core/models';
import { TourCardComponent } from '../../shared/tour-card.component';

@Component({
  selector: 'app-favorites',
  imports: [RouterLink, TranslatePipe, TourCardComponent],
  template: `
    <h1 class="h3 mb-1">{{ 'favorites.title' | translate }}</h1>
    <p class="text-muted">{{ 'favorites.subtitle' | translate }}</p>

    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else if (visible().length === 0) {
      <div class="text-center py-5">
        <div class="display-6 text-muted mb-2" aria-hidden="true">♡</div>
        <p class="text-muted">{{ 'favorites.empty' | translate }}</p>
        <a class="btn btn-primary" routerLink="/tours">{{ 'favorites.browse' | translate }}</a>
      </div>
    } @else {
      <div class="row g-3">
        @for (t of visible(); track t.id) {
          <div class="col-md-6 col-lg-4"><app-tour-card [tour]="t" /></div>
        }
      </div>
      @if (page()?.next || page()?.previous) {
        <nav class="d-flex justify-content-between align-items-center mt-4">
          <button class="btn btn-outline-secondary" [disabled]="!page()?.previous" (click)="go(pageNo() - 1)">‹ {{ 'common.prev' | translate }}</button>
          <span class="text-muted small">{{ 'common.page' | translate: { page: pageNo() } }}</span>
          <button class="btn btn-outline-secondary" [disabled]="!page()?.next" (click)="go(pageNo() + 1)">{{ 'common.next' | translate }} ›</button>
        </nav>
      }
    }
  `,
})
export class FavoritesComponent {
  private api = inject(FavoritesApi);
  private fav = inject(FavoritesService);
  private language = inject(LanguageService);

  page = signal<Page<Tour> | null>(null);
  pageNo = signal(1);
  loading = signal(true);
  failed = signal(false);
  /** a tour un-hearted on this page disappears at once (no reload needed) */
  visible = computed(() => { this.fav.count(); return (this.page()?.results ?? []).filter(t => this.fav.has(t.id)); });

  constructor() {
    effect(() => { this.language.lang(); untracked(() => this.load()); });
  }

  go(n: number): void { this.pageNo.set(n); this.load(); }

  load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api.list(this.language.lang(), this.pageNo()).subscribe({
      next: p => {
        if (p.results.length === 0 && this.pageNo() > 1) { this.go(this.pageNo() - 1); return; }
        this.page.set(p);
        this.fav.reload();          // keep hearts in sync with what the server returned
        this.loading.set(false);
      },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }
}
