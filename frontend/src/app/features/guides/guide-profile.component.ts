// Public guide profile: bio, languages, tours led, next open departures.  Owner: Aitore
// Data: GET /api/guides/<id>?lang=  (no email/phone is ever returned).
import { Component, effect, inject, input, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { ToursService } from '../../core/api.services';
import { LanguageService } from '../../core/language.service';
import { GuideProfile } from '../../core/models';
import { AppDatePipe } from '../../core/pipes';

@Component({
  selector: 'app-guide-profile',
  imports: [RouterLink, TranslatePipe, AppDatePipe],
  template: `
    <a routerLink="/tours" class="small">‹ {{ 'common.back_to_tours' | translate }}</a>

    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (notFound()) {
      <div class="alert alert-warning mt-3">{{ 'guide.not_found' | translate }}</div>
    } @else if (failed()) {
      <div class="alert alert-danger mt-3 d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else if (guide(); as g) {
      <div class="d-flex align-items-center gap-3 mt-3 mb-3">
        <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-semibold flex-shrink-0"
             style="width:64px;height:64px;font-size:1.5rem" aria-hidden="true">{{ initials(g.full_name) }}</div>
        <div>
          <div class="small text-muted">{{ 'tours.guide' | translate }}</div>
          <h1 class="h3 mb-1">{{ g.full_name }}</h1>
          <div class="small text-muted">{{ 'guide.member_since' | translate: { date: (g.member_since | appDate) } }}</div>
        </div>
      </div>

      <div class="mb-3">
        @for (l of g.languages; track l) {
          <span class="badge text-bg-light border me-1">{{ 'guide.lang_' + l | translate }}</span>
        }
        <span class="badge text-bg-primary ms-1">{{ 'guide.tours_led' | translate: { count: g.completed_count } }}</span>
      </div>

      <h2 class="h5">{{ 'guide.about' | translate }}</h2>
      <p [class.text-muted]="!g.bio">{{ g.bio || ('guide.no_bio' | translate) }}</p>

      <h2 class="h5 mt-4">{{ 'guide.upcoming' | translate }}</h2>
      @if (g.upcoming_departures.length === 0) {
        <p class="text-muted">{{ 'tours.no_departure' | translate }}</p>
      } @else {
        <div class="list-group mb-4">
          @for (d of g.upcoming_departures; track d.id) {
            <a class="list-group-item list-group-item-action d-flex flex-wrap justify-content-between align-items-center gap-2"
               [routerLink]="['/tours', d.package_id]">
              <div>
                <div class="fw-semibold">{{ d.package_title }}</div>
                <div class="small text-muted">{{ d.start_at | appDate: true }}</div>
              </div>
              @if (d.is_full) { <span class="badge text-bg-secondary">{{ 'tours.full' | translate }}</span> }
              @else { <span class="badge text-bg-success">{{ 'tours.seats_left' | translate: { count: d.seats_available } }}</span> }
            </a>
          }
        </div>
      }
    }
  `,
})
export class GuideProfileComponent {
  readonly id = input.required<string>();        // from the route /guides/:id (withComponentInputBinding)

  private toursApi = inject(ToursService);
  private language = inject(LanguageService);

  guide = signal<GuideProfile | null>(null);
  loading = signal(true);
  failed = signal(false);
  notFound = signal(false);

  constructor() {
    effect(() => { this.id(); this.language.lang(); untracked(() => this.load()); });
  }

  load(): void {
    this.loading.set(!this.guide() || this.guide()!.id !== Number(this.id()));
    this.failed.set(false);
    this.notFound.set(false);
    this.toursApi.guide(Number(this.id()), this.language.lang()).subscribe({
      next: g => { this.guide.set(g); this.loading.set(false); },
      error: e => { this.notFound.set(e?.status === 404); this.failed.set(true); this.loading.set(false); },
    });
  }

  initials(name: string): string {
    return name.split(' ').filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('');
  }
}
