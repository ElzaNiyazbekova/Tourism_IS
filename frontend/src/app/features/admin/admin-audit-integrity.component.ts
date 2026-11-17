// Admin: is the audit log still untouched? (tamper-evident hash chain).  Owner: Amina A.
import { Component, inject, signal } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';
import { AuditIntegrity, FlexService } from '../../core/flex.service';
import { AppDatePipe } from '../../core/pipes';

@Component({
  selector: 'app-admin-audit-integrity',
  imports: [TranslatePipe, AppDatePipe],
  template: `
    <h1 class="h4 mb-1">{{ 'admin.audit_integrity' | translate }}</h1>
    <p class="text-muted small">{{ 'flex.integrity.note' | translate }}</p>

    <button class="btn btn-primary btn-sm mb-3" [disabled]="loading()" (click)="check()">
      @if (loading()) { <span class="spinner-border spinner-border-sm me-1"></span> }
      {{ 'flex.integrity.check_now' | translate }}
    </button>

    @if (failed()) {
      <div class="alert alert-danger">{{ 'common.load_failed' | translate }}</div>
    }
    @if (result(); as r) {
      <div class="alert" role="status"
           [class.alert-success]="r.status === 'intact'" [class.alert-danger]="r.status === 'broken'" [class.alert-warning]="r.status === 'incomplete'">
        <strong>{{ 'flex.integrity.' + r.status | translate }}</strong>
        @if (r.first_break; as fb) {
          <div class="small mt-1">{{ 'flex.integrity.broken_at' | translate: { id: fb.audit_id } }} — {{ 'flex.integrity.reason_' + fb.reason | translate }}</div>
        }
        @if (r.status === 'incomplete') { <div class="small mt-1">{{ 'flex.integrity.incomplete_help' | translate }}</div> }
      </div>
      <dl class="row small">
        <dt class="col-sm-3">{{ 'flex.integrity.rows' | translate }}</dt><dd class="col-sm-9">{{ r.total_rows }}</dd>
        <dt class="col-sm-3">{{ 'flex.integrity.sealed' | translate }}</dt><dd class="col-sm-9">{{ r.sealed_rows }}</dd>
        <dt class="col-sm-3">{{ 'flex.integrity.unsealed' | translate }}</dt><dd class="col-sm-9">{{ r.unsealed_rows }}</dd>
        <dt class="col-sm-3">{{ 'flex.integrity.checked_at' | translate }}</dt><dd class="col-sm-9">{{ r.checked_at | appDate: true }}</dd>
        <dt class="col-sm-3">{{ 'flex.integrity.head' | translate }}</dt>
        <dd class="col-sm-9"><code class="text-break">{{ r.head_hash ?? '—' }}</code>
          <div class="text-muted">{{ 'flex.integrity.head_hint' | translate }}</div></dd>
      </dl>
    }
  `,
})
export class AdminAuditIntegrityComponent {
  private api = inject(FlexService);
  result = signal<AuditIntegrity | null>(null);
  loading = signal(false);
  failed = signal(false);

  constructor() { this.check(); }

  check(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api.integrity().subscribe({
      next: r => { this.result.set(r); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }
}
