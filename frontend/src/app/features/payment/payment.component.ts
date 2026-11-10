// Mock payment screen (functionality 3).  Owner: Aitore
// "Pay" -> Confirmed.  "Fail" -> payment row saved as Failed, the booking stays Pending.
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { BookingsService } from '../../core/api.services';
import { ApiErrorBody, BookingDetail, PayResult } from '../../core/models';
import { errorText, toApiError } from '../../core/api-error';
import { LanguageService } from '../../core/language.service';
import { AppDatePipe, AppMoneyPipe } from '../../core/pipes';

@Component({
  selector: 'app-payment',
  imports: [RouterLink, TranslatePipe, AppDatePipe, AppMoneyPipe],
  template: `
    <h1 class="h3 mb-3">{{ 'payment.title' | translate }}</h1>
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (loadError(); as e) {
      <div class="alert alert-danger d-flex justify-content-between align-items-center">
        <span>{{ errMsg(e) }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
      <a routerLink="/my-bookings">{{ 'payment.back' | translate }}</a>
    } @else if (booking(); as b) {
      <div class="card mb-3" style="max-width: 560px">
        <div class="card-body">
          <h2 class="h5">{{ b.package_title }}</h2>
          <dl class="row mb-0 small">
            <dt class="col-5">{{ 'my_bookings.ref' | translate }}</dt><dd class="col-7">{{ b.booking_ref }}</dd>
            <dt class="col-5">{{ 'my_bookings.travel_date' | translate }}</dt><dd class="col-7">{{ b.start_at | appDate: true }}</dd>
            <dt class="col-5">{{ 'booking.travelers' | translate }}</dt><dd class="col-7">{{ b.travelers_count }}</dd>
            <dt class="col-5">{{ 'my_bookings.status' | translate }}</dt>
            <dd class="col-7"><span class="badge" [class]="b.status === 'Confirmed' ? 'text-bg-success' : 'text-bg-warning'">{{ 'status.' + b.status.toLowerCase().replace(' ', '_') | translate }}</span></dd>
            <dt class="col-5">{{ 'my_bookings.total' | translate }}</dt><dd class="col-7 fw-bold">{{ b.total_cost | appMoney }}</dd>
          </dl>
        </div>
      </div>

      @if (message() === 'ok') {
        <div class="alert alert-success" role="status">{{ 'payment.success' | translate }}</div>
      } @else if (message() === 'failed') {
        <div class="alert alert-warning" role="alert">{{ 'payment.failed' | translate }}</div>
      }
      @if (error(); as e) { <div class="alert alert-danger" role="alert">{{ errMsg(e) }}</div> }

      @if (b.status === 'Pending') {
        <p class="text-muted small">{{ 'payment.mock_note' | translate }}</p>
        <div class="d-flex gap-2 mb-4">
          <button class="btn btn-success" [disabled]="paying()" (click)="pay('pay')">
            @if (paying()) { <span class="spinner-border spinner-border-sm me-1"></span> }
            {{ 'payment.pay' | translate }}
          </button>
          <button class="btn btn-outline-danger" [disabled]="paying()" (click)="pay('fail')">{{ 'payment.fail' | translate }}</button>
        </div>
      }

      <h2 class="h6">{{ 'payment.history' | translate }}</h2>
      @if (b.payments.length === 0) {
        <p class="text-muted small">{{ 'payment.no_payments' | translate }}</p>
      } @else {
        <div class="table-responsive bg-white border rounded" style="max-width: 560px">
          <table class="table table-sm mb-0">
            <thead><tr><th>{{ 'payment.reference' | translate }}</th><th>{{ 'payment.amount' | translate }}</th><th>{{ 'my_bookings.status' | translate }}</th></tr></thead>
            <tbody>
              @for (p of b.payments; track p.id) {
                <tr><td>{{ p.transaction_ref }}</td><td>{{ p.amount | appMoney }}</td>
                    <td><span class="badge" [class]="p.status === 'Success' ? 'text-bg-success' : 'text-bg-danger'">{{ 'payment.status_' + p.status.toLowerCase() | translate }}</span></td></tr>
              }
            </tbody>
          </table>
        </div>
      }
      <a routerLink="/my-bookings" class="btn btn-link ps-0 mt-3">{{ 'payment.back' | translate }}</a>
    }
  `,
})
export class PaymentComponent {
  private route = inject(ActivatedRoute);
  private api = inject(BookingsService);
  private language = inject(LanguageService);
  private translate = inject(TranslateService);

  booking = signal<BookingDetail | null>(null);
  loading = signal(true);
  loadError = signal<ApiErrorBody | null>(null);
  error = signal<ApiErrorBody | null>(null);
  message = signal<'ok' | 'failed' | null>(null);
  paying = signal(false);

  constructor() {
    effect(() => { this.language.lang(); untracked(() => this.load()); });
  }

  private get id(): number { return Number(this.route.snapshot.paramMap.get('id')); }

  load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.api.get(this.id, this.language.lang()).subscribe({
      next: b => { this.booking.set(b); this.loading.set(false); },
      error: e => { this.loadError.set(toApiError(e)); this.loading.set(false); },
    });
  }

  pay(result: 'pay' | 'fail'): void {
    this.paying.set(true);
    this.error.set(null);
    this.message.set(null);
    this.api.pay(this.id, result, this.language.lang()).subscribe({
      next: (r: PayResult) => { this.message.set(r.result === 'pay' ? 'ok' : 'failed'); this.paying.set(false); this.load(); },
      error: e => { this.error.set(toApiError(e)); this.paying.set(false); },
    });
  }

  errMsg(e: ApiErrorBody): string { return errorText(this.translate, e.message_key, e.message); }
}
