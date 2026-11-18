import { Component, effect, inject, signal, untracked } from '@angular/core';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminService } from '../../core/api.services';
import { errorText, toApiError } from '../../core/api-error';
import { LanguageService } from '../../core/language.service';
import { Page, ReviewBooking } from '../../core/models';
import { AppDatePipe, AppMoneyPipe } from '../../core/pipes';

interface Flash { kind: 'success' | 'danger'; text: string; }

@Component({
  selector: 'app-admin-bookings-review',
  imports: [TranslatePipe, AppDatePipe, AppMoneyPipe],
  template: `
    <h1 class="h4 mb-1">{{ 'admin.bookings_review' | translate }}</h1>
    <p class="text-muted small">{{ 'admin.review.note' | translate }}</p>
    @if (flash(); as f) {
      <div class="alert" [class.alert-success]="f.kind === 'success'" [class.alert-danger]="f.kind === 'danger'" role="status">{{ f.text }}</div>
    }
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else if (page(); as p) {
      @if (p.results.length === 0) {
        <div class="text-center text-muted py-5">{{ 'admin.review.empty' | translate }}</div>
      }
      @for (b of p.results; track b.id) {
        <article class="card mb-3 border-danger-subtle">
          <div class="card-body">
            <div class="d-flex flex-wrap justify-content-between align-items-start gap-2">
              <div>
                <h2 class="h6 mb-1">{{ b.booking_ref }} · {{ b.package_title }}</h2>
                <div class="small text-muted">{{ b.customer_name }} · <a [href]="'mailto:' + b.customer_email">{{ b.customer_email }}</a></div>
              </div>
              <div class="d-flex gap-1 flex-wrap">
                @if (scenario(b); as demoScenario) {
                  <span class="badge text-bg-info">{{ ('admin.review.scenario.' + demoScenario) | translate }}</span>
                }
                <span class="badge text-bg-danger">{{ 'status.needs_review' | translate }}</span>
              </div>
            </div>
            <div class="row small mt-3 g-2">
              <div class="col-sm-6"><strong>{{ 'admin.review.departure' | translate }}:</strong> {{ b.start_at | appDate: true }}</div>
              <div class="col-sm-6"><strong>{{ 'booking.travelers' | translate }}:</strong> {{ b.travelers_count }}</div>
              <div class="col-sm-6"><strong>{{ 'booking.total' | translate }}:</strong> {{ b.total_cost | appMoney }}</div>
              <div class="col-sm-6"><strong>{{ 'admin.review.created' | translate }}:</strong> {{ b.created_at | appDate: true }}</div>
              @if (b.special_request) { <div class="col-12"><strong>{{ 'admin.review.request' | translate }}:</strong> {{ b.special_request }}</div> }
            </div>
            <div class="small mt-3">
              <strong>{{ 'admin.review.payments' | translate }}:</strong>
              @if (b.payments.length) {
                @for (payment of b.payments; track payment.id) {
                  <span class="badge text-bg-light border ms-1">{{ payment.status }} · {{ payment.amount | appMoney }} · {{ payment.transaction_ref }}</span>
                }
              } @else { <span class="text-muted">{{ 'admin.review.no_payments' | translate }}</span> }
            </div>
            <div class="d-flex flex-wrap gap-2 mt-3">
              <button class="btn btn-primary btn-sm" [disabled]="busy() === b.id" (click)="fix(b)">{{ 'admin.review.fix' | translate }}</button>
              @if (mergeCandidates(b).length) {
                <div class="d-flex gap-2">
                  <select class="form-select form-select-sm" [value]="mergeTargets()[b.id] || ''" (change)="setMergeTarget(b.id, $event)" [attr.aria-label]="'admin.review.merge_target' | translate">
                    <option value="">{{ 'admin.review.merge_target' | translate }}</option>
                    @for (candidate of mergeCandidates(b); track candidate.id) {
                      <option [value]="candidate.id">{{ candidate.booking_ref }} · {{ candidate.customer_name }}</option>
                    }
                  </select>
                  <button class="btn btn-outline-primary btn-sm text-nowrap" [disabled]="busy() === b.id || !mergeTargets()[b.id]" (click)="merge(b)">{{ 'admin.review.merge' | translate }}</button>
                </div>
              }
              @if (rejecting() === b.id) {
                <button class="btn btn-danger btn-sm" [disabled]="busy() === b.id" (click)="reject(b)">{{ 'admin.review.reject_confirm' | translate }}</button>
                <button class="btn btn-outline-secondary btn-sm" (click)="rejecting.set(null)">{{ 'common.cancel' | translate }}</button>
              } @else {
                <button class="btn btn-outline-danger btn-sm" [disabled]="busy() === b.id" (click)="rejecting.set(b.id)">{{ 'admin.review.reject' | translate }}</button>
              }
            </div>
          </div>
        </article>
      }
      @if (p.count > 100) {
        <div class="d-flex justify-content-between align-items-center mt-3">
          <button class="btn btn-outline-secondary btn-sm" [disabled]="!p.previous" (click)="load(currentPage() - 1)">{{ 'common.prev' | translate }}</button>
          <span class="small text-muted">{{ 'common.page' | translate: { page: currentPage() } }}</span>
          <button class="btn btn-outline-secondary btn-sm" [disabled]="!p.next" (click)="load(currentPage() + 1)">{{ 'common.next' | translate }}</button>
        </div>
      }
    }
  `,
})
export class AdminBookingsReviewComponent {
  private api = inject(AdminService);
  private language = inject(LanguageService);
  private translate = inject(TranslateService);

  page = signal<Page<ReviewBooking> | null>(null);
  currentPage = signal(1);
  loading = signal(true);
  failed = signal(false);
  busy = signal<number | null>(null);
  rejecting = signal<number | null>(null);
  mergeTargets = signal<Record<number, number>>({});
  flash = signal<Flash | null>(null);

  constructor() { effect(() => { this.language.lang(); untracked(() => this.load(1)); }); }

  load(page = this.currentPage()): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api.reviewBookings(this.language.lang(), page).subscribe({
      next: result => { this.page.set(result); this.currentPage.set(page); this.loading.set(false); },
      error: error => { this.failed.set(true); this.loading.set(false); this.showError(error); },
    });
  }

  mergeCandidates(booking: ReviewBooking): ReviewBooking[] {
    return (this.page()?.results ?? []).filter(candidate => candidate.id !== booking.id
      && candidate.departure_id === booking.departure_id && candidate.customer_email === booking.customer_email
      && candidate.status === 'Needs review');
  }

  scenario(booking: ReviewBooking): string | null {
    const request = booking.special_request;
    if (!request.startsWith('[review-demo]')) return null;
    if (request.includes('no successful payment')) return 'fix_pending';
    if (request.includes('successful payment')) return 'fix_confirmed';
    if (request.includes('MERGE:')) return 'merge';
    if (request.includes('REJECT:')) return 'reject';
    return 'example';
  }

  setMergeTarget(id: number, event: Event): void {
    const value = Number((event.target as HTMLSelectElement).value);
    this.mergeTargets.update(targets => ({ ...targets, [id]: value || 0 }));
  }

  fix(booking: ReviewBooking): void {
    this.run(booking.id, this.api.fixReviewBooking(booking.id, this.language.lang()),
      result => this.translate.instant(result.status === 'Confirmed' ? 'admin.review.fixed_confirmed' : 'admin.review.fixed_pending'));
  }

  merge(booking: ReviewBooking): void {
    const target = this.mergeTargets()[booking.id];
    if (!target) return;
    this.run(booking.id, this.api.mergeReviewBooking(booking.id, target, this.language.lang()),
      result => this.translate.instant('admin.review.merged', { ref: result.booking_ref }));
  }

  reject(booking: ReviewBooking): void {
    this.run(booking.id, this.api.rejectReviewBooking(booking.id, this.language.lang()),
      () => this.translate.instant('admin.review.rejected'));
  }

  private run(id: number, request: import('rxjs').Observable<ReviewBooking>, message: (result: ReviewBooking) => string): void {
    this.busy.set(id);
    this.flash.set(null);
    request.subscribe({
      next: result => { this.busy.set(null); this.rejecting.set(null); this.flash.set({ kind: 'success', text: message(result) }); this.load(); },
      error: error => { this.busy.set(null); this.showError(error); this.load(); },
    });
  }

  private showError(error: unknown): void {
    const apiError = toApiError(error);
    this.flash.set({ kind: 'danger', text: errorText(this.translate, apiError.message_key, apiError.message) });
  }
}