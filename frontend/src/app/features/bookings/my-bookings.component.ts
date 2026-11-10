// "My bookings" (functionality 2).  Owner: Aitore
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { BookingsService } from '../../core/api.services';
import { LanguageService } from '../../core/language.service';
import { Booking, Page } from '../../core/models';
import { AppDatePipe, AppMoneyPipe } from '../../core/pipes';

@Component({
  selector: 'app-my-bookings',
  imports: [RouterLink, TranslatePipe, AppDatePipe, AppMoneyPipe],
  template: `
    <h1 class="h3 mb-3">{{ 'my_bookings.title' | translate }}</h1>
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else if (page()?.results?.length === 0) {
      <div class="text-center text-muted py-5">
        <p>{{ 'my_bookings.empty' | translate }}</p>
        <a routerLink="/tours" class="btn btn-primary">{{ 'common.back_to_tours' | translate }}</a>
      </div>
    } @else {
      <div class="table-responsive bg-white border rounded">
        <table class="table align-middle mb-0">
          <thead><tr>
            <th>{{ 'my_bookings.ref' | translate }}</th><th>{{ 'my_bookings.tour' | translate }}</th>
            <th>{{ 'my_bookings.travel_date' | translate }}</th><th>{{ 'booking.travelers' | translate }}</th>
            <th>{{ 'my_bookings.total' | translate }}</th><th>{{ 'my_bookings.status' | translate }}</th>
          </tr></thead>
          <tbody>
            @for (b of page()?.results; track b.id) {
              <tr>
                <td class="fw-semibold">{{ b.booking_ref }}</td>
                <td><a [routerLink]="['/tours', b.package_id]">{{ b.package_title }}</a>
                    <div class="small text-muted">{{ b.guide_name }}</div></td>
                <td>{{ b.start_at | appDate: true }}</td>
                <td>{{ b.travelers_count }}</td>
                <td>{{ b.total_cost | appMoney }}</td>
                <td>
                  <span class="badge" [class]="badge(b)">{{ statusKey(b) | translate }}</span>
                  @if (b.status === 'Pending') {
                    <a class="btn btn-sm btn-success mt-1" [routerLink]="['/pay', b.id]">{{ 'my_bookings.pay_now' | translate }}</a>
                  }
                  @if (b.status === 'Pending' && b.expires_at) {
                    <div class="small text-muted">{{ 'my_bookings.pay_before' | translate }} {{ b.expires_at | appDate: true }}</div>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <nav class="d-flex justify-content-between align-items-center mt-3">
        <button class="btn btn-outline-secondary" [disabled]="!page()?.previous" (click)="go(pageNo() - 1)">‹ {{ 'common.prev' | translate }}</button>
        <span class="text-muted small">{{ 'common.page' | translate: { page: pageNo() } }} · {{ page()?.count }}</span>
        <button class="btn btn-outline-secondary" [disabled]="!page()?.next" (click)="go(pageNo() + 1)">{{ 'common.next' | translate }} ›</button>
      </nav>
    }
  `,
})
export class MyBookingsComponent {
  private api = inject(BookingsService);
  private language = inject(LanguageService);

  page = signal<Page<Booking> | null>(null);
  pageNo = signal(1);
  loading = signal(true);
  failed = signal(false);

  constructor() {
    effect(() => { this.language.lang(); untracked(() => this.load()); });
  }

  go(n: number): void { this.pageNo.set(n); this.load(); }

  load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api.mine(this.language.lang(), this.pageNo()).subscribe({
      next: p => { this.page.set(p); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }

  statusKey(b: Booking): string { return 'status.' + b.status.toLowerCase().replace(' ', '_'); }
  badge(b: Booking): string {
    const map: Record<string, string> = { Pending: 'text-bg-warning', Confirmed: 'text-bg-success', Cancelled: 'text-bg-secondary',
                                          Completed: 'text-bg-primary', 'Needs review': 'text-bg-danger' };
    return 'badge ' + (map[b.status] ?? 'text-bg-light');
  }
}
