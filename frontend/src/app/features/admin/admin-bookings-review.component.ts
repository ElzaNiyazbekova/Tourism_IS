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
    <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-3">
      <div>
        <h1 class="h4 mb-1">{{ 'admin.bookings_review' | translate }}</h1>
        <p class="text-muted small mb-0">{{ 'admin.review.note' | translate }}</p>
      </div>
      @if (page(); as p) {
        <span class="badge rounded-pill text-bg-warning px-3 py-2">{{ p.count }} {{ 'admin.review.cards' | translate }}</span>
      }
    </div>

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
        <div class="card border-0 shadow-sm">
          <div class="card-body text-center py-5">
            <div class="display-6 mb-2">✓</div>
            <h2 class="h6">{{ 'admin.review.empty' | translate }}</h2>
          </div>
        </div>
      }

      @for (b of p.results; track b.id) {
        <article class="card border-0 shadow-sm mb-3 overflow-hidden">
          <div class="border-start border-4 border-warning">
            <div class="card-body p-4">
              <div class="d-flex flex-wrap justify-content-between align-items-start gap-3">
                <div>
                  <div class="small text-uppercase text-muted mb-1">{{ 'admin.review.booking' | translate }}</div>
                  <h2 class="h5 mb-1">{{ b.booking_ref }}</h2>
                  <div class="text-muted">{{ b.package_title }}</div>
                </div>
                <span class="badge rounded-pill text-bg-warning px-3 py-2">{{ 'admin.review.status_mismatch' | translate }}</span>
              </div>

              <div class="row g-3 mt-2">
                <div class="col-md-7">
                  <div class="rounded-3 bg-light border p-3 h-100">
                    <div class="small text-muted mb-2">{{ 'admin.review.issue' | translate }}</div>
                    <div class="fw-semibold mb-3">{{ ('admin.review.exception.' + b.exception_reason) | translate }}</div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                      <span class="badge rounded-pill px-3 py-2" [class.text-bg-danger]="b.status === 'Expired'" [class.text-bg-warning]="b.status === 'Pending'" [class.text-bg-success]="b.status === 'Confirmed'" [class.text-bg-secondary]="b.status === 'Completed'">
                        {{ ('status.' + b.status.toLowerCase()) | translate }}
                      </span>
                      <span class="text-muted fs-5">→</span>
                      <span class="badge rounded-pill text-bg-primary px-3 py-2">
                        {{ ('status.' + b.suggested_status.toLowerCase()) | translate }}
                      </span>
                    </div>
                  </div>
                </div>

                <div class="col-md-5">
                  <div class="rounded-3 bg-light border p-3 h-100">
                    <div class="small text-muted mb-2">{{ 'admin.review.customer' | translate }}</div>
                    <div class="fw-semibold">{{ b.customer_name }}</div>
                    <a class="small" [href]="'mailto:' + b.customer_email">{{ b.customer_email }}</a>
                  </div>
                </div>
              </div>

              <div class="row g-2 mt-1">
                <div class="col-sm-6 col-lg-3">
                  <div class="border rounded-3 p-3 h-100">
                    <div class="small text-muted">{{ 'admin.review.departure' | translate }}</div>
                    <div class="fw-semibold small mt-1">{{ b.start_at | appDate: true }}</div>
                  </div>
                </div>
                <div class="col-sm-6 col-lg-3">
                  <div class="border rounded-3 p-3 h-100">
                    <div class="small text-muted">{{ 'booking.travelers' | translate }}</div>
                    <div class="fw-semibold mt-1">{{ b.travelers_count }}</div>
                  </div>
                </div>
                <div class="col-sm-6 col-lg-3">
                  <div class="border rounded-3 p-3 h-100">
                    <div class="small text-muted">{{ 'booking.total' | translate }}</div>
                    <div class="fw-semibold mt-1">{{ b.total_cost | appMoney }}</div>
                  </div>
                </div>
                <div class="col-sm-6 col-lg-3">
                  <div class="border rounded-3 p-3 h-100">
                    <div class="small text-muted">{{ 'admin.review.suggested' | translate }}</div>
                    <div class="fw-semibold mt-1">{{ ('status.' + b.suggested_status.toLowerCase()) | translate }}</div>
                  </div>
                </div>
              </div>

              <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 mt-3 pt-3 border-top">
                <div class="small text-muted">
                  {{ 'admin.review.created' | translate }}: {{ b.created_at | appDate: true }}
                </div>
                <button class="btn btn-primary px-4" [disabled]="busy() === b.id" (click)="fix(b)">
                  @if (busy() === b.id) { <span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span> }
                  {{ 'admin.review.fix' | translate }}
                </button>
              </div>
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

  fix(booking: ReviewBooking): void {
    this.run(booking.id, this.api.fixReviewBooking(booking.id, this.language.lang()),
      result => this.translate.instant('admin.review.fixed_status', { status: result.status }));
  }

  private run(id: number, request: import('rxjs').Observable<ReviewBooking>, message: (result: ReviewBooking) => string): void {
    this.busy.set(id);
    this.flash.set(null);
    request.subscribe({
      next: result => { this.busy.set(null); this.flash.set({ kind: 'success', text: message(result) }); this.load(); },
      error: error => { this.busy.set(null); this.showError(error); this.load(); },
    });
  }

  private showError(error: unknown): void {
    const apiError = toApiError(error);
    this.flash.set({ kind: 'danger', text: errorText(this.translate, apiError.message_key, apiError.message) });
  }
}