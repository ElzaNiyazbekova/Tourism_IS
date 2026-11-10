// Admin: list of departures with deactivate / activate.  Owner: Aitore
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminService } from '../../core/api.services';
import { AdminDeparture, ApiErrorBody, Page } from '../../core/models';
import { errorText, toApiError } from '../../core/api-error';
import { LanguageService } from '../../core/language.service';
import { AppDatePipe } from '../../core/pipes';

@Component({
  selector: 'app-admin-departures',
  imports: [RouterLink, TranslatePipe, AppDatePipe],
  template: `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h4 mb-0">{{ 'admin.departures' | translate }}</h1>
      <a class="btn btn-primary" routerLink="/admin/departures/new">{{ 'admin.new_departure' | translate }}</a>
    </div>
    @if (error(); as e) { <div class="alert alert-danger">{{ errMsg(e) }}</div> }
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between"><span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button></div>
    } @else if (page()?.results?.length === 0) {
      <p class="text-muted text-center py-5">{{ 'admin.no_departures' | translate }}</p>
    } @else {
      <div class="table-responsive bg-white border rounded">
        <table class="table align-middle mb-0">
          <thead><tr><th>{{ 'admin.col_title' | translate }}</th><th>{{ 'tours.guide' | translate }}</th><th>{{ 'admin.start' | translate }}</th>
            <th>{{ 'admin.seats' | translate }}</th><th>{{ 'my_bookings.status' | translate }}</th><th></th></tr></thead>
          <tbody>
            @for (d of page()?.results; track d.id) {
              <tr>
                <td class="fw-semibold">{{ d.package_title }}</td><td>{{ d.guide_name }}</td><td>{{ d.start_at | appDate: true }}</td>
                <td>{{ d.booked_seats }} / {{ d.seats_total }}</td>
                <td><span class="badge" [class]="d.is_active ? 'text-bg-success' : 'text-bg-secondary'">{{ (d.is_active ? 'admin.active' : 'admin.inactive') | translate }}</span></td>
                <td class="text-end text-nowrap">
                  <a class="btn btn-sm btn-outline-primary me-1" [routerLink]="['/admin/departures', d.id]">{{ 'admin.edit' | translate }}</a>
                  <button class="btn btn-sm" [class]="d.is_active ? 'btn-outline-danger' : 'btn-outline-success'" [disabled]="busy() === d.id" (click)="toggle(d)">
                    {{ (d.is_active ? 'admin.deactivate' : 'admin.activate') | translate }}</button>
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
export class AdminDeparturesComponent {
  private api = inject(AdminService);
  private language = inject(LanguageService);
  private translate = inject(TranslateService);
  page = signal<Page<AdminDeparture> | null>(null);
  pageNo = signal(1);
  loading = signal(true);
  failed = signal(false);
  busy = signal<number | null>(null);
  error = signal<ApiErrorBody | null>(null);

  constructor() { effect(() => { this.language.lang(); untracked(() => this.load()); }); }

  go(n: number): void { this.pageNo.set(n); this.load(); }
  load(): void {
    this.loading.set(true); this.failed.set(false);
    this.api.departures(this.language.lang(), this.pageNo()).subscribe({
      next: p => { this.page.set(p); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }
  toggle(d: AdminDeparture): void {
    this.busy.set(d.id); this.error.set(null);
    this.api.setDepartureActive(d.id, !d.is_active).subscribe({
      next: () => { this.busy.set(null); this.load(); },
      error: e => { this.error.set(toApiError(e)); this.busy.set(null); },
    });
  }
  errMsg(e: ApiErrorBody): string { return errorText(this.translate, e.message_key, e.message); }
}
