// Admin: create / edit a departure. Shows the guide-overlap error and the next free slot.  Owner: Aitore
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminService } from '../../core/api.services';
import { AdminDeparture, AdminGuide, AdminTour, ApiErrorBody } from '../../core/models';
import { errorText, fieldErrorText, toApiError } from '../../core/api-error';
import { LanguageService } from '../../core/language.service';
import { AppDatePipe } from '../../core/pipes';

const TZ = 'Asia/Almaty';          // fixed UTC+05:00, same zone the pages display
/** ISO instant -> value for <input type="datetime-local"> in Almaty time */
const toLocalInput = (iso: string) => new Intl.DateTimeFormat('sv-SE', { timeZone: TZ, dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso)).replace(' ', 'T');
const fromLocalInput = (v: string | null): string => (v ? `${v}:00+05:00` : '');

@Component({
  selector: 'app-admin-departure-form',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe, AppDatePipe],
  template: `
    <h1 class="h4 mb-3">{{ (id ? 'admin.edit_departure' : 'admin.new_departure') | translate }}</h1>
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (loadFailed()) {
      <div class="alert alert-danger">{{ 'common.load_failed' | translate }}</div>
    } @else {
      @if (error(); as e) {
        <div class="alert alert-danger" role="alert">{{ errMsg(e) }}
          @if (e.next_available_departure; as n) { <div class="small mt-1">{{ 'booking.next_available' | translate: { date: (n.start_at | appDate: true) } }}</div> }
        </div>
      }
      <form [formGroup]="form" (ngSubmit)="save()" class="bg-white border rounded p-3" novalidate style="max-width: 720px">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label" for="pkg">{{ 'admin.tour' | translate }}</label>
            <select id="pkg" class="form-select" formControlName="package" [class.is-invalid]="fe('package')">
              <option [ngValue]="null" disabled>—</option>
              @for (t of tours(); track t.id) { <option [ngValue]="t.id">{{ t.title }}</option> }
            </select>
            <div class="invalid-feedback">{{ fe('package') }}</div>
          </div>
          <div class="col-md-6">
            <label class="form-label" for="gd">{{ 'tours.guide' | translate }}</label>
            <select id="gd" class="form-select" formControlName="guide" [class.is-invalid]="fe('guide')">
              <option [ngValue]="null" disabled>—</option>
              @for (g of guides(); track g.id) { <option [ngValue]="g.id">{{ g.full_name }}</option> }
            </select>
            <div class="invalid-feedback">{{ fe('guide') }}</div>
          </div>
          <div class="col-md-4">
            <label class="form-label" for="st">{{ 'admin.start' | translate }}</label>
            <input id="st" type="datetime-local" class="form-control" formControlName="start_at" [class.is-invalid]="fe('start_at')">
            <div class="invalid-feedback">{{ fe('start_at') }}</div>
          </div>
          <div class="col-md-4">
            <label class="form-label" for="en">{{ 'admin.end' | translate }}</label>
            <input id="en" type="datetime-local" class="form-control" formControlName="end_at" [class.is-invalid]="fe('end_at')">
            <div class="invalid-feedback">{{ fe('end_at') }}</div>
          </div>
          <div class="col-md-4">
            <label class="form-label" for="seats">{{ 'admin.seats_total' | translate }}</label>
            <input id="seats" type="number" min="1" class="form-control" formControlName="seats_total" [class.is-invalid]="fe('seats_total')">
            <div class="invalid-feedback">{{ fe('seats_total') }}</div>
          </div>
        </div>
        <div class="d-flex gap-2 mt-3">
          <button class="btn btn-primary" type="submit" [disabled]="saving()">
            @if (saving()) { <span class="spinner-border spinner-border-sm me-1"></span> }{{ 'admin.save' | translate }}</button>
          <a class="btn btn-outline-secondary" routerLink="/admin/departures">{{ 'common.cancel' | translate }}</a>
        </div>
      </form>
    }
  `,
})
export class AdminDepartureFormComponent {
  private fb = inject(FormBuilder);
  private api = inject(AdminService);
  private router = inject(Router);
  private translate = inject(TranslateService);
  private language = inject(LanguageService);
  readonly id: number | null = Number(inject(ActivatedRoute).snapshot.paramMap.get('id')) || null;

  tours = signal<AdminTour[]>([]);
  guides = signal<AdminGuide[]>([]);
  loading = signal(true);
  loadFailed = signal(false);
  saving = signal(false);
  error = signal<ApiErrorBody | null>(null);

  form = this.fb.group({
    package: this.fb.control<number | null>(null, Validators.required),
    guide: this.fb.control<number | null>(null, Validators.required),
    start_at: ['', Validators.required],
    end_at: ['', Validators.required],
    seats_total: this.fb.control<number | null>(10, [Validators.required, Validators.min(1)]),
  });

  constructor() {
    const lang = this.language.lang();
    this.api.tours(lang, 1).subscribe({
      next: t => {
        this.tours.set(t.results.filter(x => x.is_active));
        this.api.guides().subscribe({
          next: g => {
            this.guides.set(g.filter(x => x.is_active));
            if (!this.id) { this.loading.set(false); return; }
            this.api.departure(this.id, lang).subscribe({
              next: d => { this.fill(d); this.loading.set(false); },
              error: () => { this.loadFailed.set(true); this.loading.set(false); },
            });
          },
          error: () => { this.loadFailed.set(true); this.loading.set(false); },
        });
      },
      error: () => { this.loadFailed.set(true); this.loading.set(false); },
    });
  }

  private fill(d: AdminDeparture): void {
    this.form.patchValue({ package: d.package, guide: d.guide, start_at: toLocalInput(d.start_at), end_at: toLocalInput(d.end_at), seats_total: d.seats_total });
  }

  save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const v = this.form.getRawValue();
    if (!v.start_at || !v.end_at) return;
    this.saving.set(true); this.error.set(null);
    const body = { package: v.package, guide: v.guide, start_at: fromLocalInput(v.start_at), end_at: fromLocalInput(v.end_at), seats_total: v.seats_total };
    this.api.saveDeparture(this.id, body, this.language.lang()).subscribe({
      next: () => this.router.navigate(['/admin/departures']),
      error: e => { this.error.set(toApiError(e)); this.saving.set(false); },
    });
  }

  fe(field: string): string { return fieldErrorText(this.translate, this.error(), field); }
  errMsg(e: ApiErrorBody): string { return errorText(this.translate, e.message_key, e.message); }
}
