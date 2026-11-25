// /admin shell: sidebar + outlet. Analyst sees only Reports.  Owner: Aitore
import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-admin-layout',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, TranslatePipe],
  template: `
    <div class="row">
      <aside class="col-md-3 col-lg-2 mb-3">
        <h2 class="h6 text-uppercase text-muted">{{ 'admin.title' | translate }}</h2>
        <div class="list-group">
          @if (staff()) {
            <a class="list-group-item list-group-item-action" routerLink="/admin/tours" routerLinkActive="active">{{ 'admin.tours' | translate }}</a>
            <a class="list-group-item list-group-item-action" routerLink="/admin/departures" routerLinkActive="active">{{ 'admin.departures' | translate }}</a>
            <a class="list-group-item list-group-item-action" routerLink="/admin/dashboard" routerLinkActive="active">{{ 'admin.dashboard' | translate }}</a>
            <a class="list-group-item list-group-item-action" routerLink="/admin/bookings" routerLinkActive="active">{{ 'admin.bookings' | translate }}</a>
            <a class="list-group-item list-group-item-action" routerLink="/admin/review-queue" routerLinkActive="active">{{ 'admin.review_queue' | translate }}</a>
          }
          @if (isAdmin()) {
            <a class="list-group-item list-group-item-action" routerLink="/admin/audit" routerLinkActive="active">{{ 'admin.audit' | translate }}</a>
            <a class="list-group-item list-group-item-action" routerLink="/admin/audit-integrity" routerLinkActive="active">{{ 'admin.audit_integrity' | translate }}</a>
          }
          <a class="list-group-item list-group-item-action" routerLink="/admin/reports" routerLinkActive="active">{{ 'admin.reports' | translate }}</a>
        </div>
      </aside>
      <section class="col-md-9 col-lg-10"><router-outlet /></section>
    </div>
  `,
})
export class AdminLayoutComponent {
  private auth = inject(AuthService);
  isAdmin = () => this.auth.role() === 'admin';
  staff = () => ['manager', 'admin'].includes(this.auth.role() ?? '');
}
