// Tour detail + departures (guide, time, seats left) + the booking panel.  Owner: Aitore
// Booking errors (full / duplicate / past) are shown with their translated message and
// the guide's NEXT available departure (Lab 4 acceptance criterion).
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { BookingsService, ToursService } from '../../core/api.services';
import { LanguageService } from '../../core/language.service';
import { AuthService } from '../../core/auth.service';
import { ApiErrorBody, Booking, Departure, TourDetail } from '../../core/models';
import { AppDatePipe, AppMoneyPipe } from '../../core/pipes';
import { errorText, toApiError } from '../../core/api-error';

@Component({
  selector: 'app-tour-detail',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe, AppDatePipe, AppMoneyPipe],
  template: `
    <a routerLink="/tours" class="small">‹ {{ 'common.back_to_tours' | translate }}</a>

    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger mt-3 d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else if (tour(); as t) {
      <div class="mt-2">
        <div class="small text-muted">{{ t.destination.name }}, {{ t.destination.country }}</div>
        <h1 class="h3">{{ t.title }}</h1>
        <p>{{ t.description }}</p>
        <div class="mb-4">
          <span class="badge text-bg-primary me-1">{{ t.base_price | appMoney }}</span>
          <span class="badge text-bg-light border me-1">{{ 'common.days' | translate: { count: t.duration_days } }}</span>
          @if (t.accommodation_included) { <span class="badge text-bg-light border me-1">{{ 'tours.accommodation' | translate }}</span> }
          @if (t.transport_included) { <span class="badge text-bg-light border me-1">{{ 'tours.transport' | translate }}</span> }
        </div>
      </div>

      @if (booked(); as b) {
        <div class="alert alert-success" role="status">
          {{ 'booking.success' | translate: { ref: b.booking_ref } }}
          <a [routerLink]="['/pay', b.id]" class="alert-link ms-2">{{ 'my_bookings.pay_now' | translate }}</a>
          <a routerLink="/my-bookings" class="alert-link ms-2">{{ 'booking.view_mine' | translate }}</a>
        </div>
      }

      <h2 class="h5">{{ 'tours.departures' | translate }}</h2>
      @if (t.departures.length === 0) {
        <p class="text-muted">{{ 'tours.no_departure' | translate }}</p>
      } @else {
        <div class="list-group mb-4">
          @for (d of t.departures; track d.id) {
            <div class="list-group-item">
              <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                <div>
                  <div class="fw-semibold">{{ d.start_at | appDate: true }}</div>
                  <div class="small text-muted">{{ 'tours.guide' | translate }}: {{ d.guide.full_name }} · {{ d.guide.languages.join(', ') }}</div>
                </div>
                <div class="d-flex align-items-center gap-2">
                  @if (d.is_full) { <span class="badge text-bg-secondary">{{ 'tours.full' | translate }}</span> }
                  @else { <span class="badge text-bg-success">{{ 'tours.seats_left' | translate: { count: d.seats_available } }}</span> }
                  @if (!d.is_full) {
                    @if (!auth.isLoggedIn()) {
                      <a class="btn btn-sm btn-primary" routerLink="/login" [queryParams]="{ returnUrl: '/tours/' + t.id }">{{ 'tours.login_to_book' | translate }}</a>
                    } @else if (auth.role() === 'tourist') {
                      <button class="btn btn-sm btn-primary" (click)="select(d)">{{ 'tours.book' | translate }}</button>
                    }
                  }
                </div>
              </div>

              @if (selected()?.id === d.id) {
                <form class="border-top mt-3 pt-3" [formGroup]="form" (ngSubmit)="confirm(t)" novalidate>
                  <h3 class="h6">{{ 'booking.form_title' | translate }}</h3>
                  @if (error(); as e) {
                    <div class="alert alert-danger" role="alert">
                      {{ errMsg(e) }}
                      @if (e.next_available_departure; as n) {
                        <div class="mt-1">
                          {{ 'booking.next_available' | translate: { date: (n.start_at | appDate: true) } }}
                          <a class="alert-link ms-1" [routerLink]="['/tours', n.package_id]">{{ 'booking.open_tour' | translate }}</a>
                        </div>
                      }
                    </div>
                  }
                  <div class="row g-3">
                    <div class="col-sm-3">
                      <label class="form-label small" [for]="'tc' + d.id">{{ 'booking.travelers' | translate }}</label>
                      <input [id]="'tc' + d.id" type="number" class="form-control" formControlName="travelers_count" min="1" [max]="d.seats_available">
                    </div>
                    <div class="col-sm-9">
                      <label class="form-label small" [for]="'sr' + d.id">{{ 'booking.special_request' | translate }}</label>
                      <input [id]="'sr' + d.id" class="form-control" formControlName="special_request" maxlength="500">
                    </div>
                  </div>
                  <div class="d-flex justify-content-between align-items-center mt-3">
                    <div>{{ 'booking.total' | translate }}: <strong>{{ total() | appMoney }}</strong></div>
                    <div>
                      <button type="button" class="btn btn-outline-secondary me-2" (click)="selected.set(null)">{{ 'common.cancel' | translate }}</button>
                      <button class="btn btn-success" type="submit" [disabled]="form.invalid || submitting()">
                        @if (submitting()) { <span class="spinner-border spinner-border-sm me-1"></span> }
                        {{ 'booking.confirm' | translate }}
                      </button>
                    </div>
                  </div>
                </form>
              }
            </div>
          }
        </div>
      }

      <h2 class="h5">{{ 'tours.reviews' | translate }}</h2>
      @if (t.reviews.length === 0) {
        <p class="text-muted">{{ 'tours.no_reviews' | translate }}</p>
      } @else {
        @for (r of t.reviews; track r.id) {
          <div class="border rounded p-2 mb-2 bg-white">
            <span class="text-warning">{{ stars(r.rating) }}</span> <strong class="ms-1">{{ r.author }}</strong>
            <span class="text-muted small ms-2">{{ r.created_at | appDate }}</span>
            <div>{{ r.comment }}</div>
          </div>
        }
      }
    }
  `,
})
export class TourDetailComponent {
  readonly id = input.required<string>();        // from the route /tours/:id (withComponentInputBinding)

  private toursApi = inject(ToursService);
  private bookingsApi = inject(BookingsService);
  private translate = inject(TranslateService);
  private fb = inject(FormBuilder);
  private language = inject(LanguageService);
  auth = inject(AuthService);

  tour = signal<TourDetail | null>(null);
  loading = signal(true);
  failed = signal(false);
  selected = signal<Departure | null>(null);
  submitting = signal(false);
  error = signal<ApiErrorBody | null>(null);
  booked = signal<Booking | null>(null);

  form = this.fb.nonNullable.group({
    travelers_count: [1, [Validators.required, Validators.min(1), Validators.max(50)]],
    special_request: ['', Validators.maxLength(500)],
  });
  private travelers = signal(1);
  total = computed(() => Number(this.tour()?.base_price ?? 0) * this.travelers());

  constructor() {
    this.form.controls.travelers_count.valueChanges.subscribe(v => this.travelers.set(Number(v) || 0));
    effect(() => { this.id(); this.language.lang(); untracked(() => this.load()); });
  }

  load(): void {
    this.loading.set(!this.tour());          // keep showing the old data while reloading after a language switch
    this.failed.set(false);
    this.toursApi.detail(Number(this.id()), this.language.lang()).subscribe({
      next: t => { this.tour.set(t); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }

  select(d: Departure): void {
    this.selected.set(d);
    this.error.set(null);
    this.booked.set(null);
    this.form.reset({ travelers_count: 1, special_request: '' });
  }

  confirm(t: TourDetail): void {
    const d = this.selected();
    if (!d || this.form.invalid) return;
    this.submitting.set(true);
    this.error.set(null);
    const v = this.form.getRawValue();
    this.bookingsApi.create({ departure: d.id, travelers_count: Number(v.travelers_count), special_request: v.special_request }, this.language.lang())
      .subscribe({
        next: b => { this.booked.set(b); this.selected.set(null); this.submitting.set(false); this.load(); },
        error: e => { this.error.set(toApiError(e)); this.submitting.set(false); },
      });
  }

  errMsg(e: ApiErrorBody): string { return errorText(this.translate, e.message_key, e.message); }
  stars(n: number): string { return '★'.repeat(n) + '☆'.repeat(5 - n); }
}
