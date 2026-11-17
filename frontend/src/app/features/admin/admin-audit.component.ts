// Admin: audit log (who changed what, when). READ-ONLY.  Owner: Amina A. / Aitore
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { KeyValuePipe } from '@angular/common';
import { TranslatePipe } from '@ngx-translate/core';
import { AuditService } from '../../core/api.services';
import { AuditEntry, AuditFacets, Page } from '../../core/models';
import { AppDatePipe } from '../../core/pipes';

@Component({
  selector: 'app-admin-audit',
  imports: [ReactiveFormsModule, KeyValuePipe, TranslatePipe, AppDatePipe],
  template: `
    <h1 class="h4 mb-1">{{ 'admin.audit' | translate }}</h1>
    <p class="text-muted small">{{ 'admin.audit_note' | translate }}</p>

    <form [formGroup]="filters" (ngSubmit)="apply()" class="row g-2 align-items-end mb-3">
      <div class="col-6 col-md-3">
        <label class="form-label small" for="at">{{ 'admin.audit_table' | translate }}</label>
        <select id="at" class="form-select form-select-sm" formControlName="table">
          <option value="">{{ 'admin.audit_all' | translate }}</option>
          @for (t of facets().tables; track t) { <option [value]="t">{{ t }}</option> }
        </select>
      </div>
      <div class="col-6 col-md-3">
        <label class="form-label small" for="aa">{{ 'admin.audit_action' | translate }}</label>
        <select id="aa" class="form-select form-select-sm" formControlName="action">
          <option value="">{{ 'admin.audit_all' | translate }}</option>
          @for (a of facets().actions; track a) { <option [value]="a">{{ a }}</option> }
        </select>
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small" for="af">{{ 'admin.audit_from' | translate }}</label>
        <input id="af" type="date" class="form-control form-control-sm" formControlName="date_from">
      </div>
      <div class="col-6 col-md-2">
        <label class="form-label small" for="ato">{{ 'admin.audit_to' | translate }}</label>
        <input id="ato" type="date" class="form-control form-control-sm" formControlName="date_to">
      </div>
      <div class="col-12 col-md-2 d-flex gap-2">
        <button class="btn btn-sm btn-primary" type="submit">{{ 'tours.apply' | translate }}</button>
        <button class="btn btn-sm btn-outline-secondary" type="button" (click)="reset()">{{ 'admin.audit_reset' | translate }}</button>
      </div>
    </form>

    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between"><span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button></div>
    } @else if (page()?.results?.length === 0) {
      <p class="text-muted text-center py-5">{{ 'admin.audit_empty' | translate }}</p>
    } @else {
      <div class="table-responsive bg-white border rounded">
        <table class="table table-sm align-middle mb-0">
          <thead><tr><th>{{ 'admin.audit_when' | translate }}</th><th>{{ 'admin.audit_who' | translate }}</th>
            <th>{{ 'admin.audit_action' | translate }}</th><th>{{ 'admin.audit_table' | translate }}</th><th>#</th><th></th></tr></thead>
          <tbody>
            @for (e of page()?.results; track e.id) {
              <tr>
                <td class="text-nowrap">{{ e.created_at | appDate: true }}</td>
                <td>@if (e.user) { {{ e.user.full_name }} <span class="badge text-bg-light border">{{ e.user.role }}</span> }
                    @else { <span class="text-muted">{{ 'admin.audit_system' | translate }}</span> }</td>
                <td><span class="badge text-bg-secondary">{{ e.action }}</span></td>
                <td>{{ e.table_name }}</td><td>{{ e.record_id }}</td>
                <td class="text-end">
                  @if (e.old_value || e.new_value) {
                    <button class="btn btn-sm btn-link py-0" (click)="toggle(e.id)" [attr.aria-expanded]="open() === e.id">
                      {{ (open() === e.id ? 'admin.audit_hide' : 'admin.audit_details') | translate }}</button>
                  }
                </td>
              </tr>
              @if (open() === e.id) {
                <tr><td colspan="6" class="bg-light">
                  <div class="row small">
                    <div class="col-md-6"><strong>{{ 'admin.audit_before' | translate }}</strong>
                      @if (e.old_value) { <dl class="mb-0">@for (kv of e.old_value | keyvalue; track kv.key) { <dt class="d-inline">{{ kv.key }}:</dt> <dd class="d-inline">{{ show(kv.value) }}</dd><br> }</dl> } @else { <div class="text-muted">—</div> }</div>
                    <div class="col-md-6"><strong>{{ 'admin.audit_after' | translate }}</strong>
                      @if (e.new_value) { <dl class="mb-0">@for (kv of e.new_value | keyvalue; track kv.key) { <dt class="d-inline">{{ kv.key }}:</dt> <dd class="d-inline" [class.fw-bold]="changed(e, kv.key)">{{ show(kv.value) }}</dd><br> }</dl> } @else { <div class="text-muted">—</div> }</div>
                  </div>
                </td></tr>
              }
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
export class AdminAuditComponent {
  private api = inject(AuditService);
  private fb = inject(FormBuilder);

  filters = this.fb.nonNullable.group({ table: '', action: '', date_from: '', date_to: '' });
  page = signal<Page<AuditEntry> | null>(null);
  facets = signal<AuditFacets>({ tables: [], actions: [] });
  pageNo = signal(1);
  open = signal<number | null>(null);
  loading = signal(true);
  failed = signal(false);

  constructor() {
    this.api.facets().subscribe({ next: f => this.facets.set(f), error: () => {} });   // dropdowns are optional
    this.load();
  }

  apply(): void { this.pageNo.set(1); this.load(); }
  reset(): void { this.filters.reset(); this.apply(); }
  go(n: number): void { this.pageNo.set(n); this.load(); }
  toggle(id: number): void { this.open.set(this.open() === id ? null : id); }

  load(): void {
    this.loading.set(true); this.failed.set(false); this.open.set(null);
    this.api.list(this.filters.getRawValue(), this.pageNo()).subscribe({
      next: p => { this.page.set(p); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }

  show(v: unknown): string { return v !== null && typeof v === 'object' ? JSON.stringify(v) : String(v); }
  changed(e: AuditEntry, key: string): boolean { return !!e.old_value && JSON.stringify(e.old_value[key]) !== JSON.stringify(e.new_value?.[key]); }
}
