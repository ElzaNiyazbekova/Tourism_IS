// Analyst view: counts per package. AGGREGATE ONLY - the API returns no names, emails or phones.  Owner: Dastan / Aitore
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';
import { AnalyticsService } from '../../core/api.services';
import { PackageReport } from '../../core/models';
import { LanguageService } from '../../core/language.service';
import { AppMoneyPipe } from '../../core/pipes';

@Component({
  selector: 'app-admin-reports',
  imports: [TranslatePipe, AppMoneyPipe],
  template: `
    <h1 class="h4 mb-1">{{ 'admin.reports' | translate }}</h1>
    <p class="text-muted small">{{ 'admin.reports_note' | translate }}</p>
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between"><span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button></div>
    } @else if (report(); as r) {
      @if (r.packages.length === 0) {
        <p class="text-muted text-center py-5">{{ 'admin.no_tours' | translate }}</p>
      } @else {
        <div class="table-responsive bg-white border rounded">
          <table class="table align-middle mb-0">
            <thead><tr><th>{{ 'admin.col_title' | translate }}</th><th>{{ 'tours.destination' | translate }}</th>
              <th class="text-end">{{ 'admin.active_bookings' | translate }}</th><th class="text-end">{{ 'admin.completed' | translate }}</th>
              <th class="text-end">{{ 'admin.cancelled' | translate }}</th><th class="text-end">{{ 'admin.revenue' | translate }}</th></tr></thead>
            <tbody>
              @for (p of r.packages; track p.package_id) {
                <tr><td class="fw-semibold">{{ p.title }}</td><td>{{ p.destination }}</td>
                  <td class="text-end">{{ p.active_bookings }}</td><td class="text-end">{{ p.completed_bookings }}</td>
                  <td class="text-end">{{ p.cancelled_bookings }}</td><td class="text-end">{{ p.revenue | appMoney }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      }
    }
  `,
})
export class AdminReportsComponent {
  private api = inject(AnalyticsService);
  private language = inject(LanguageService);
  report = signal<PackageReport | null>(null);
  loading = signal(true);
  failed = signal(false);

  constructor() { effect(() => { this.language.lang(); untracked(() => this.load()); }); }

  load(): void {
    this.loading.set(true); this.failed.set(false);
    this.api.packages(this.language.lang()).subscribe({
      next: r => { this.report.set(r); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }
}
