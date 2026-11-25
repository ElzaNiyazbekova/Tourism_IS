// Guide cabinet: stats, own departures with travellers, edit own public profile.  Owner: Aitore
// Data: GET/PATCH /api/guide/me, GET /api/guide/departures?when=, GET /api/guide/departures/<id>  (role "guide" only)
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { GuideCabinetService } from '../../core/api.services';
import { LanguageService } from '../../core/language.service';
import { CabinetDeparture, CabinetDepartureDetail, GuideMe, Lang, Page } from '../../core/models';
import { AppDatePipe } from '../../core/pipes';

type When = 'upcoming' | 'past';

@Component({
  selector: 'app-guide-cabinet',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe, AppDatePipe],
  template: `
    <h1 class="h3 mb-1">{{ 'cabinet.title' | translate }}</h1>
    <p class="text-muted">{{ 'cabinet.subtitle' | translate }}</p>

    @if (me(); as g) {
      @if (!g.is_active) { <div class="alert alert-warning">{{ 'cabinet.inactive' | translate }}</div> }
      <div class="row g-3 mb-4">
        @for (s of stats; track s.key) {
          <div class="col-4">
            <div class="card card-body text-center h-100">
              <div class="display-6 fw-semibold">{{ g[s.key] }}</div>
              <div class="small text-muted">{{ s.label | translate }}</div>
            </div>
          </div>
        }
      </div>
    }

    <div class="row g-4">
      <!-- departures -->
      <section class="col-lg-8">
        <ul class="nav nav-tabs mb-3">
          @for (w of tabs; track w) {
            <li class="nav-item">
              <button type="button" class="nav-link" [class.active]="when() === w" (click)="switchTab(w)">{{ 'cabinet.tab_' + w | translate }}</button>
            </li>
          }
        </ul>

        @if (loading()) {
          <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
        } @else if (failed()) {
          <div class="alert alert-danger d-flex justify-content-between align-items-center">
            <span>{{ 'common.load_failed' | translate }}</span>
            <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
          </div>
        } @else if (page()?.results?.length === 0) {
          <div class="text-center text-muted py-5">{{ 'cabinet.empty_' + when() | translate }}</div>
        } @else {
          <div class="list-group">
            @for (d of page()?.results; track d.id) {
              <div class="list-group-item">
                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                  <div>
                    <a class="fw-semibold" [routerLink]="['/tours', d.package_id]">{{ d.package_title }}</a>
                    <span class="small text-muted"> · {{ d.destination }}</span>
                    <div class="small">{{ d.start_at | appDate: true }} — {{ d.end_at | appDate: true }}</div>
                    <div class="small text-muted">
                      {{ 'cabinet.booked' | translate: { bookings: d.bookings_count, travelers: d.travelers_count } }} ·
                      {{ 'cabinet.seats' | translate: { taken: d.seats_total - d.seats_available, total: d.seats_total } }}
                    </div>
                  </div>
                  <div class="d-flex align-items-center gap-2">
                    @if (!d.is_active) { <span class="badge text-bg-secondary">{{ 'cabinet.cancelled_departure' | translate }}</span> }
                    <button type="button" class="btn btn-sm btn-outline-primary" (click)="toggle(d)" [attr.aria-expanded]="openId() === d.id">
                      {{ (openId() === d.id ? 'cabinet.hide_travelers' : 'cabinet.show_travelers') | translate }}
                    </button>
                  </div>
                </div>

                @if (openId() === d.id) {
                  <div class="mt-3">
                    @if (detail(); as det) {
                      @if (det.travelers.length === 0) {
                        <p class="text-muted small mb-0">{{ 'cabinet.no_travelers' | translate }}</p>
                      } @else {
                        <div class="table-responsive">
                          <table class="table table-sm align-middle mb-0">
                            <thead><tr>
                              <th>{{ 'cabinet.col_name' | translate }}</th><th>{{ 'cabinet.col_phone' | translate }}</th>
                              <th>{{ 'cabinet.col_group' | translate }}</th><th>{{ 'cabinet.col_status' | translate }}</th>
                              <th>{{ 'cabinet.col_request' | translate }}</th>
                            </tr></thead>
                            <tbody>
                              @for (t of det.travelers; track t.booking_ref) {
                                <tr>
                                  <td>{{ t.full_name }}<div class="small text-muted">{{ t.booking_ref }}</div></td>
                                  <td>@if (t.phone) { <a [href]="'tel:' + t.phone">{{ t.phone }}</a> } @else { — }</td>
                                  <td>{{ 'cabinet.group_size' | translate: { count: t.travelers_count } }}</td>
                                  <td><span class="badge" [class]="statusClass(t.status)">{{ statusKey(t.status) | translate }}</span></td>
                                  <td class="small">{{ t.special_request || '—' }}</td>
                                </tr>
                              }
                            </tbody>
                          </table>
                        </div>
                      }
                    } @else if (detailFailed()) {
                      <div class="text-danger small">{{ 'common.load_failed' | translate }}</div>
                    } @else {
                      <div class="spinner-border spinner-border-sm" role="status"></div>
                    }
                  </div>
                }
              </div>
            }
          </div>

          @if (page()?.next || page()?.previous) {
            <nav class="d-flex justify-content-between align-items-center mt-3">
              <button class="btn btn-outline-secondary btn-sm" [disabled]="!page()?.previous" (click)="go(pageNo() - 1)">‹ {{ 'common.prev' | translate }}</button>
              <span class="text-muted small">{{ 'common.page' | translate: { page: pageNo() } }}</span>
              <button class="btn btn-outline-secondary btn-sm" [disabled]="!page()?.next" (click)="go(pageNo() + 1)">{{ 'common.next' | translate }} ›</button>
            </nav>
          }
        }
      </section>

      <!-- profile -->
      <section class="col-lg-4">
        <form class="card card-body" [formGroup]="form" (ngSubmit)="save()">
          <h2 class="h5">{{ 'cabinet.profile' | translate }}</h2>
          <label class="form-label small" for="g-bio">{{ 'cabinet.bio' | translate }}</label>
          <textarea id="g-bio" class="form-control" rows="5" maxlength="2000" formControlName="bio"></textarea>
          <div class="form-text mb-3">{{ 'cabinet.bio_hint' | translate }}</div>

          <div class="small mb-1">{{ 'cabinet.languages' | translate }}</div>
          @for (l of langs; track l) {
            <div class="form-check">
              <input class="form-check-input" type="checkbox" [id]="'g-lang-' + l" [checked]="hasLang(l)" (change)="toggleLang(l)">
              <label class="form-check-label" [for]="'g-lang-' + l">{{ 'guide.lang_' + l | translate }}</label>
            </div>
          }
          @if (form.controls.languages.value.length === 0) {
            <div class="text-danger small">{{ 'cabinet.languages_required' | translate }}</div>
          }

          <button class="btn btn-primary mt-3" type="submit" [disabled]="form.invalid || saving()">{{ 'cabinet.save' | translate }}</button>
          @if (saveMsg(); as m) { <div class="small mt-2" [class.text-success]="m === 'cabinet.saved'" [class.text-danger]="m !== 'cabinet.saved'">{{ m | translate }}</div> }
          @if (me(); as g) { <a class="small mt-3" [routerLink]="['/guides', g.id]">{{ 'cabinet.view_public' | translate }} ›</a> }
        </form>
      </section>
    </div>
  `,
})
export class GuideCabinetComponent {
  private api = inject(GuideCabinetService);
  private language = inject(LanguageService);
  private fb = inject(FormBuilder);

  readonly tabs: When[] = ['upcoming', 'past'];
  readonly langs: Lang[] = ['kk', 'ru', 'en'];
  readonly stats = [
    { key: 'upcoming_count', label: 'cabinet.upcoming_count' },
    { key: 'travelers_upcoming', label: 'cabinet.travelers_upcoming' },
    { key: 'completed_count', label: 'cabinet.completed_count' },
  ] as const;

  me = signal<GuideMe | null>(null);
  when = signal<When>('upcoming');
  page = signal<Page<CabinetDeparture> | null>(null);
  pageNo = signal(1);
  loading = signal(true);
  failed = signal(false);
  openId = signal<number | null>(null);
  detail = signal<CabinetDepartureDetail | null>(null);
  detailFailed = signal(false);
  saving = signal(false);
  saveMsg = signal('');

  form = this.fb.nonNullable.group({
    bio: ['', Validators.maxLength(2000)],
    languages: this.fb.nonNullable.control<Lang[]>([], c => (c.value as Lang[]).length ? null : { required: true }),
  });

  constructor() {
    this.loadMe();
    // tour titles come translated from the API -> reload the list when the UI language changes
    effect(() => { this.language.lang(); untracked(() => { this.openId.set(null); this.load(); }); });
  }

  private loadMe(): void {
    this.api.me().subscribe({ next: g => this.applyMe(g), error: () => {} });
  }

  private applyMe(g: GuideMe): void {
    this.me.set(g);
    this.form.reset({ bio: g.bio, languages: [...g.languages] });
  }

  switchTab(w: When): void {
    if (this.when() === w) return;
    this.when.set(w);
    this.pageNo.set(1);
    this.openId.set(null);
    this.load();
  }

  go(n: number): void { this.pageNo.set(n); this.openId.set(null); this.load(); }

  load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api.departures(this.when(), this.language.lang(), this.pageNo()).subscribe({
      next: p => { this.page.set(p); this.loading.set(false); },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }

  toggle(d: CabinetDeparture): void {
    if (this.openId() === d.id) { this.openId.set(null); return; }
    this.openId.set(d.id);
    this.detail.set(null);
    this.detailFailed.set(false);
    this.api.departure(d.id, this.language.lang()).subscribe({
      next: det => { if (this.openId() === det.id) this.detail.set(det); },
      error: () => this.detailFailed.set(true),
    });
  }

  hasLang(l: Lang): boolean { return this.form.controls.languages.value.includes(l); }

  toggleLang(l: Lang): void {
    const cur = this.form.controls.languages.value;
    this.form.controls.languages.setValue(cur.includes(l) ? cur.filter(x => x !== l) : [...cur, l]);
    this.form.markAsDirty();
    this.saveMsg.set('');
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    this.saveMsg.set('');
    this.api.updateMe(this.form.getRawValue()).subscribe({
      next: g => { this.applyMe(g); this.saving.set(false); this.saveMsg.set('cabinet.saved'); },
      error: () => { this.saving.set(false); this.saveMsg.set('cabinet.save_failed'); },
    });
  }

  statusKey(s: string): string { return 'status.' + s.toLowerCase().replace(' ', '_'); }

  statusClass(s: string): string {
    return ({ Confirmed: 'text-bg-success', Pending: 'text-bg-warning', Completed: 'text-bg-secondary' } as Record<string, string>)[s]
      ?? 'text-bg-light border';
  }
}
