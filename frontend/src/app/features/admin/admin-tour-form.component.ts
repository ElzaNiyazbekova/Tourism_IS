// Admin: create / edit a tour with EN + RU + KK titles.  Owner: Aitore
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminService } from '../../core/api.services';
import { ApiErrorBody, AdminTour, Destination, Lang } from '../../core/models';
import { errorText, fieldErrorText, toApiError } from '../../core/api-error';
import { LanguageService } from '../../core/language.service';

const LANGS: Lang[] = ['en', 'ru', 'kk'];

@Component({
  selector: 'app-admin-tour-form',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe],
  template: `
    <h1 class="h4 mb-3">{{ (id ? 'admin.edit_tour' : 'admin.new_tour') | translate }}</h1>
    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (loadFailed()) {
      <div class="alert alert-danger">{{ 'common.load_failed' | translate }}</div>
    } @else {
      @if (error(); as e) { <div class="alert alert-danger" role="alert">{{ errMsg(e) }}</div> }
      <form [formGroup]="form" (ngSubmit)="save()" class="bg-white border rounded p-3" novalidate style="max-width: 720px">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label" for="dest">{{ 'tours.destination' | translate }}</label>
            <select id="dest" class="form-select" formControlName="destination" [class.is-invalid]="fe('destination')">
              <option [ngValue]="null" disabled>—</option>
              @for (d of destinations(); track d.id) { <option [ngValue]="d.id">{{ d.name }}, {{ d.country }}</option> }
            </select>
            <div class="invalid-feedback">{{ fe('destination') }}</div>
          </div>
          <div class="col-md-3">
            <label class="form-label" for="price">{{ 'admin.col_price' | translate }}</label>
            <input id="price" type="number" min="0" step="0.01" class="form-control" formControlName="base_price" [class.is-invalid]="fe('base_price')">
            <div class="invalid-feedback">{{ fe('base_price') }}</div>
          </div>
          <div class="col-md-3">
            <label class="form-label" for="dur">{{ 'admin.duration' | translate }}</label>
            <input id="dur" type="number" min="1" class="form-control" formControlName="duration_days" [class.is-invalid]="fe('duration_days')">
            <div class="invalid-feedback">{{ fe('duration_days') }}</div>
          </div>
          <div class="col-12">
            <div class="form-check form-check-inline"><input id="acc" type="checkbox" class="form-check-input" formControlName="accommodation_included"><label class="form-check-label" for="acc">{{ 'tours.accommodation' | translate }}</label></div>
            <div class="form-check form-check-inline"><input id="trn" type="checkbox" class="form-check-input" formControlName="transport_included"><label class="form-check-label" for="trn">{{ 'tours.transport' | translate }}</label></div>
          </div>
        </div>
        <hr>
        @for (l of langs; track l) {
          <fieldset class="mb-3" [formGroupName]="l">
            <legend class="h6">{{ 'admin.lang_' + l | translate }} @if (l === 'en') { <span class="text-danger">*</span> }</legend>
            <input class="form-control mb-2" formControlName="title" [attr.aria-label]="'admin.col_title' | translate" [placeholder]="'admin.col_title' | translate"
                   [class.is-invalid]="form.get(l + '.title')?.touched && form.get(l + '.title')?.invalid">
            <textarea class="form-control" rows="3" formControlName="description" [attr.aria-label]="'admin.description' | translate" [placeholder]="'admin.description' | translate"></textarea>
          </fieldset>
        }
        @if (fe('translations'); as m) { <div class="text-danger small mb-2">{{ m }}</div> }
        <div class="d-flex gap-2">
          <button class="btn btn-primary" type="submit" [disabled]="saving()">
            @if (saving()) { <span class="spinner-border spinner-border-sm me-1"></span> }{{ 'admin.save' | translate }}</button>
          <a class="btn btn-outline-secondary" routerLink="/admin/tours">{{ 'common.cancel' | translate }}</a>
        </div>
      </form>
    }
  `,
})
export class AdminTourFormComponent {
  private fb = inject(FormBuilder);
  private api = inject(AdminService);
  private router = inject(Router);
  private translate = inject(TranslateService);
  private language = inject(LanguageService);
  readonly id: number | null = Number(inject(ActivatedRoute).snapshot.paramMap.get('id')) || null;
  readonly langs = LANGS;

  destinations = signal<Destination[]>([]);
  loading = signal(true);
  loadFailed = signal(false);
  saving = signal(false);
  error = signal<ApiErrorBody | null>(null);

  form = this.fb.group({
    destination: this.fb.control<number | null>(null, Validators.required),
    base_price: this.fb.control<number | null>(null, [Validators.required, Validators.min(0)]),
    duration_days: this.fb.control<number | null>(1, [Validators.required, Validators.min(1)]),
    accommodation_included: this.fb.control(false),
    transport_included: this.fb.control(false),
    en: this.fb.group({ title: ['', Validators.required], description: [''] }),
    ru: this.fb.group({ title: [''], description: [''] }),
    kk: this.fb.group({ title: [''], description: [''] }),
  });

  constructor() {
    this.api.destinations().subscribe({
      next: d => {
        this.destinations.set(d);
        if (!this.id) { this.loading.set(false); return; }
        this.api.tour(this.id, this.language.lang()).subscribe({
          next: t => { this.fill(t); this.loading.set(false); },
          error: () => { this.loadFailed.set(true); this.loading.set(false); },
        });
      },
      error: () => { this.loadFailed.set(true); this.loading.set(false); },
    });
  }

  private fill(t: AdminTour): void {
    this.form.patchValue({ destination: t.destination, base_price: Number(t.base_price), duration_days: t.duration_days,
      accommodation_included: t.accommodation_included, transport_included: t.transport_included });
    for (const tr of t.translations) this.form.get(tr.language_code)?.patchValue({ title: tr.title, description: tr.description });
  }

  save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
    const v = this.form.getRawValue();
    const translations = LANGS.flatMap(l => {
      const row = v[l] as { title?: string | null; description?: string | null } | null;
      const title = (row?.title ?? '').trim();
      if (!title) return [];
      return [{ language_code: l, title, description: row?.description ?? '' }];
    });
    this.saving.set(true); this.error.set(null);
    const body = { destination: v.destination, base_price: String(v.base_price), duration_days: v.duration_days,
      accommodation_included: v.accommodation_included, transport_included: v.transport_included, translations };
    this.api.saveTour(this.id, body, this.language.lang()).subscribe({
      next: () => this.router.navigate(['/admin/tours']),
      error: e => { this.error.set(toApiError(e)); this.saving.set(false); },
    });
  }

  fe(field: string): string { return fieldErrorText(this.translate, this.error(), field); }
  errMsg(e: ApiErrorBody): string { return errorText(this.translate, e.message_key, e.message); }
}
