// Admin: list of tours with deactivate / activate.  Owner: Aitore
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminService } from '../../core/api.services';
import { ApiErrorBody, AdminTour, Page } from '../../core/models';
import { errorText, toApiError } from '../../core/api-error';
import { LanguageService } from '../../core/language.service';
import { AppMoneyPipe } from '../../core/pipes';

@Component({
  selector: 'app-admin-tours',
  imports: [RouterLink, TranslatePipe, AppMoneyPipe],
  template: `
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h4 mb-0">{{ 'admin.tours' | translate }}</h1>
      <a class="btn btn-primary" routerLink="/admin/tours/new">{{ 'admin.new_tour' | translate }}</a>
    </div>
    @if (error(); as e) { <div class="alert alert-danger">{{ errMsg(e) }}</div> }
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between"><span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button></div>
    } @else if (page()?.results?.length === 0) {
      <p class="text-muted text-center py-5">{{ 'admin.no_tours' | translate }}</p>
    } @else {
      <div class="table-responsive bg-white border rounded">
        <table class="table align-middle mb-0">
          <thead><tr><th>{{ 'admin.col_title' | translate }}</th><th>{{ 'tours.destination' | translate }}</th>
            <th>{{ 'admin.col_price' | translate }}</th><th>{{ 'my_bookings.status' | translate }}</th><th></th></tr></thead>
          <tbody>
            @for (t of page()?.results; track t.id) {
              <tr>
                <td class="fw-semibold">{{ t.title }}</td><td>{{ t.destination_name }}</td><td>{{ t.base_price | appMoney }}</td>
                <td><span class="badge" [class]="t.is_active ? 'text-bg-success' : 'text-bg-secondary'">{{ (t.is_active ? 'admin.active' : 'admin.inactive') | translate }}</span></td>
                <td class="text-end text-nowrap">
                  <a class="btn btn-sm btn-outline-primary me-1" [routerLink]="['/admin/tours', t.id]">{{ 'admin.edit' | translate }}</a>
                  <button class="btn btn-sm" [class]="t.is_active ? 'btn-outline-danger' : 'btn-outline-success'" [disabled]="busy() === t.id" (click)="toggle(t)">
                    {{ (t.is_active ? 'admin.deactivate' : 'admin.activate') | translate }}</button>
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
export class AdminToursComponent {
  private api = inject(AdminService);
  private language = inject(LanguageService);
  private translate = inject(TranslateService);
  page = signal<Page<AdminTour> | null>(null);
  pageNo = signal(1);
  loading = signal(true);
  failed = signal(false);
  busy = signal<number | null>(null);
  error = signal<ApiErrorBody | null>(null);

  constructor() { effect(() => { this.language.lang(); untracked(() => this.load()); }); }

  go(n: number): void { this.pageNo.set(n); this.load(); }
  load(): void {
    this.loading.set(true); this.failed.set(false);
    this.api.tours(this.language.lang(), this.pageNo()).subscribe({
      next: p => { this.page.set(p); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }
  toggle(t: AdminTour): void {
    this.busy.set(t.id); this.error.set(null);
    this.api.setTourActive(t.id, !t.is_active).subscribe({
      next: () => { this.busy.set(null); this.load(); },
      error: e => { this.error.set(toApiError(e)); this.busy.set(null); },
    });
  }
  errMsg(e: ApiErrorBody): string { return errorText(this.translate, e.message_key, e.message); }
}
