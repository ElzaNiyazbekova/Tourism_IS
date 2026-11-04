// Tour catalogue with filters + pagination; loading / empty / error states.  Owner: Aitore
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { ToursService } from '../../core/api.services';
import { LanguageService } from '../../core/language.service';
import { Destination, Page, Tour } from '../../core/models';
import { AppDatePipe, AppMoneyPipe } from '../../core/pipes';

@Component({
  selector: 'app-tour-list',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe, AppDatePipe, AppMoneyPipe],
  template: `
    <h1 class="h3 mb-1">{{ 'tours.title' | translate }}</h1>
    <p class="text-muted">{{ 'tours.subtitle' | translate }}</p>

    <form class="row g-2 align-items-end mb-4" [formGroup]="filters" (ngSubmit)="apply()">
      <div class="col-md-3">
        <label class="form-label small" for="f-dest">{{ 'tours.destination' | translate }}</label>
        <select id="f-dest" class="form-select" formControlName="destination">
          <option value="">{{ 'tours.all_destinations' | translate }}</option>
          @for (d of destinations(); track d.id) { <option [value]="d.id">{{ d.name }}</option> }
        </select>
      </div>
      <div class="col-md-2">
        <label class="form-label small" for="f-min">{{ 'tours.price_min' | translate }}</label>
        <input id="f-min" type="number" min="0" class="form-control" formControlName="price_min">
      </div>
      <div class="col-md-2">
        <label class="form-label small" for="f-max">{{ 'tours.price_max' | translate }}</label>
        <input id="f-max" type="number" min="0" class="form-control" formControlName="price_max">
      </div>
      <div class="col-md-3">
        <label class="form-label small" for="f-ord">{{ 'tours.sort' | translate }}</label>
        <select id="f-ord" class="form-select" formControlName="ordering">
          <option value="">{{ 'tours.sort_default' | translate }}</option>
          <option value="price">{{ 'tours.sort_price_asc' | translate }}</option>
          <option value="-price">{{ 'tours.sort_price_desc' | translate }}</option>
          <option value="next">{{ 'tours.sort_soonest' | translate }}</option>
          <option value="rating">{{ 'tours.sort_rating' | translate }}</option>
        </select>
      </div>
      <div class="col-md-2 d-grid"><button class="btn btn-primary" type="submit">{{ 'tours.apply' | translate }}</button></div>
    </form>

    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div>
        <div class="text-muted mt-2">{{ 'common.loading' | translate }}</div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else if (page()?.results?.length === 0) {
      <div class="text-center text-muted py-5">{{ 'tours.empty' | translate }}</div>
    } @else {
      <div class="row g-3">
        @for (t of page()?.results; track t.id) {
          <div class="col-md-6 col-lg-4">
            <a class="card h-100 card-hover text-body" [routerLink]="['/tours', t.id]">
              <div class="card-body d-flex flex-column">
                <div class="small text-muted">{{ t.destination.name }}, {{ t.destination.country }}</div>
                <h2 class="h5 mt-1">{{ t.title }}</h2>
                <p class="small text-muted flex-grow-1">{{ t.description }}</p>
                <div class="mb-2">
                  @if (t.accommodation_included) { <span class="badge text-bg-light border me-1">{{ 'tours.accommodation' | translate }}</span> }
                  @if (t.transport_included) { <span class="badge text-bg-light border me-1">{{ 'tours.transport' | translate }}</span> }
                  <span class="badge text-bg-light border">{{ 'common.days' | translate: { count: t.duration_days } }}</span>
                </div>
                <div class="d-flex justify-content-between align-items-end">
                  <div>
                    <div class="fw-bold">{{ 'tours.from_price' | translate }} {{ t.base_price | appMoney }}</div>
                    <div class="small text-muted">
                      @if (t.next_departure_at) { {{ 'tours.next_departure' | translate }}: {{ t.next_departure_at | appDate }} }
                      @else { {{ 'tours.no_departure' | translate }} }
                    </div>
                  </div>
                  @if (t.avg_rating !== null) { <span class="badge text-bg-warning">★ {{ t.avg_rating.toFixed(1) }} ({{ t.review_count }})</span> }
                </div>
              </div>
            </a>
          </div>
        }
      </div>

      <nav class="d-flex justify-content-between align-items-center mt-4">
        <button class="btn btn-outline-secondary" [disabled]="!page()?.previous" (click)="go(pageNo() - 1)">‹ {{ 'common.prev' | translate }}</button>
        <span class="text-muted small">{{ 'common.page' | translate: { page: pageNo() } }} · {{ page()?.count }}</span>
        <button class="btn btn-outline-secondary" [disabled]="!page()?.next" (click)="go(pageNo() + 1)">{{ 'common.next' | translate }} ›</button>
      </nav>
    }
  `,
})
export class TourListComponent {
  private tours = inject(ToursService);
  private fb = inject(FormBuilder);
  private language = inject(LanguageService);

  destinations = signal<Destination[]>([]);
  page = signal<Page<Tour> | null>(null);
  pageNo = signal(1);
  loading = signal(true);
  failed = signal(false);
  filters = this.fb.nonNullable.group({ destination: '', price_min: '', price_max: '', ordering: '' });

  constructor() {
    this.tours.destinations().subscribe({ next: p => this.destinations.set(p.results), error: () => {} });
    // reload whenever the UI language changes (titles/descriptions come translated from the API)
    effect(() => { this.language.lang(); untracked(() => this.load()); });
  }

  apply(): void { this.pageNo.set(1); this.load(); }
  go(n: number): void { this.pageNo.set(n); this.load(); }

  load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.tours.list(this.filters.getRawValue(), this.language.lang(), this.pageNo()).subscribe({
      next: p => { this.page.set(p); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }
}
