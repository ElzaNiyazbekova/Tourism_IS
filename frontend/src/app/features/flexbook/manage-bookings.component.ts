// "Manage my trips": cancel with preview, 10-minute undo, seat handover, booking history.  Owner: Amina A.
// The server decides what is allowed (/api/bookings/flex-state); this screen only shows the buttons it is told to.
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { BookingsService } from '../../core/api.services';
import { errorText, fieldErrorText, toApiError } from '../../core/api-error';
import { CancelPreview, FlexService, FlexState, IncomingHandover, Timeline } from '../../core/flex.service';
import { LanguageService } from '../../core/language.service';
import { ApiErrorBody, Booking } from '../../core/models';
import { AppDatePipe, AppMoneyPipe } from '../../core/pipes';

interface Flash { kind: 'success' | 'danger'; text: string; }

@Component({
  selector: 'app-manage-bookings',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe, AppDatePipe, AppMoneyPipe],
  template: `
    <h1 class="h3 mb-1">{{ 'flex.title' | translate }}</h1>
    <p class="text-muted">{{ 'flex.subtitle' | translate }}</p>

    @if (flash(); as f) {
      <div class="alert" [class.alert-success]="f.kind === 'success'" [class.alert-danger]="f.kind === 'danger'" role="status">{{ f.text }}</div>
    }

    @if (loading()) {
      <div class="text-center py-5"><div class="spinner-border" role="status"></div></div>
    } @else if (failed()) {
      <div class="alert alert-danger d-flex justify-content-between align-items-center">
        <span>{{ 'common.load_failed' | translate }}</span>
        <button class="btn btn-sm btn-outline-danger" (click)="load()">{{ 'common.retry' | translate }}</button>
      </div>
    } @else {
      @if (incoming().length) {
        <h2 class="h5 mt-3">{{ 'flex.incoming_title' | translate }}</h2>
        @for (o of incoming(); track o.id) {
          <div class="card border-primary mb-2">
            <div class="card-body d-flex flex-wrap justify-content-between gap-2 align-items-center">
              <div>
                <div class="fw-semibold">{{ o.package_title }} · {{ o.start_at | appDate: true }}</div>
                <div class="small text-muted">
                  {{ 'flex.from' | translate: { name: o.from_name } }} · {{ o.booking_ref }} · {{ 'booking.travelers' | translate }}: {{ o.travelers_count }} · {{ o.total_cost | appMoney }}
                </div>
                @if (o.message) { <div class="small fst-italic">“{{ o.message }}”</div> }
                <div class="small text-muted">{{ 'flex.valid_until' | translate }} {{ o.expires_at | appDate: true }}</div>
                @if (o.booking_status === 'Pending') { <div class="small text-warning-emphasis">{{ 'flex.pending_note' | translate }}</div> }
              </div>
              <div class="d-flex gap-2">
                <button class="btn btn-primary btn-sm" [disabled]="busy() === 'o' + o.id" (click)="accept(o)">{{ 'flex.accept' | translate }}</button>
                <button class="btn btn-outline-secondary btn-sm" [disabled]="busy() === 'o' + o.id" (click)="decline(o)">{{ 'flex.decline' | translate }}</button>
              </div>
            </div>
          </div>
        }
      }

      <h2 class="h5 mt-4">{{ 'flex.upcoming' | translate }}</h2>
      @if (trips().length === 0) {
        <div class="text-center text-muted py-5">
          <p>{{ 'flex.none' | translate }}</p>
          <a routerLink="/tours" class="btn btn-primary">{{ 'common.back_to_tours' | translate }}</a>
        </div>
      }
      @for (t of trips(); track t.b.id) {
        <div class="card mb-3">
          <div class="card-body">
            <div class="d-flex flex-wrap justify-content-between gap-2">
              <div>
                <div class="fw-semibold">{{ t.b.booking_ref }} · <a [routerLink]="['/tours', t.b.package_id]">{{ t.b.package_title }}</a></div>
                <div class="small text-muted">{{ t.b.start_at | appDate: true }} · {{ t.b.guide_name }} · {{ 'booking.travelers' | translate }}: {{ t.b.travelers_count }} · {{ t.b.total_cost | appMoney }}</div>
              </div>
              <span class="badge align-self-start" [class]="badge(t.b)">{{ 'status.' + t.b.status.toLowerCase().replace(' ', '_') | translate }}</span>
            </div>

            <div class="d-flex flex-wrap gap-2 mt-3">
              @if (t.b.status === 'Pending') {
                <a class="btn btn-success btn-sm" [routerLink]="['/pay', t.b.id]">{{ 'my_bookings.pay_now' | translate }}</a>
              }
              @if (t.s.can_cancel) {
                <button class="btn btn-outline-danger btn-sm" [disabled]="busy() === t.b.id" (click)="askCancel(t.b)">{{ 'flex.cancel' | translate }}</button>
              }
              @if (t.s.can_undo) {
                <button class="btn btn-warning btn-sm" [disabled]="busy() === t.b.id" (click)="undo(t.b)">{{ 'flex.undo' | translate }}</button>
              }
              @if (t.s.can_handover) {
                <button class="btn btn-outline-primary btn-sm" (click)="openHandover(t.b.id)">{{ 'flex.handover' | translate }}</button>
              }
              <button class="btn btn-link btn-sm" (click)="toggleTimeline(t.b.id)" [attr.aria-expanded]="timelineOpen() === t.b.id">
                {{ (timelineOpen() === t.b.id ? 'flex.hide_history' : 'flex.history') | translate }}</button>
            </div>

            @if (t.s.can_undo && t.s.undo_until) {
              <div class="small text-muted mt-2">{{ 'flex.undo_hint' | translate: { time: (t.s.undo_until | appDate: true) } }}</div>
            }
            @if (t.b.status !== 'Cancelled' && !t.s.can_cancel) {
              <div class="small text-muted mt-2">{{ 'flex.cancel_closed' | translate: { date: (t.s.cancel_deadline | appDate: true) } }}</div>
            }
            @if (t.s.handover; as h) {
              <div class="alert alert-info py-2 mt-2 mb-0 d-flex flex-wrap justify-content-between align-items-center gap-2">
                <span class="small">{{ 'flex.offer_pending' | translate: { email: h.to_email, date: (h.expires_at | appDate: true) } }}</span>
                <button class="btn btn-sm btn-outline-secondary" [disabled]="busy() === 'w' + h.id" (click)="withdraw(h.id)">{{ 'flex.withdraw' | translate }}</button>
              </div>
            }

            @if (confirming(); as c) {
              @if (c.id === t.b.id) {
                <div class="border rounded p-3 mt-3 bg-light">
                  <div class="fw-semibold">{{ 'flex.cancel_confirm_title' | translate: { ref: t.b.booking_ref } }}</div>
                  <ul class="small mb-2">
                    <li>{{ 'flex.cancel_seats' | translate: { n: c.preview.seats_returned } }}</li>
                    <li>{{ 'flex.cancel_deadline' | translate: { date: (c.preview.deadline | appDate: true) } }}</li>
                    <li>{{ 'flex.cancel_undo_note' | translate: { minutes: c.preview.undo_minutes } }}</li>
                    @if (c.preview.was_paid) { <li>{{ 'flex.cancel_paid_note' | translate }}</li> }
                  </ul>
                  <button class="btn btn-danger btn-sm me-2" [disabled]="busy() === t.b.id" (click)="doCancel(t.b)">{{ 'flex.cancel_go' | translate }}</button>
                  <button class="btn btn-outline-secondary btn-sm" (click)="confirming.set(null)">{{ 'flex.cancel_keep' | translate }}</button>
                </div>
              }
            }

            @if (handoverFor() === t.b.id) {
              <form class="border rounded p-3 mt-3 bg-light" [formGroup]="handoverForm" (ngSubmit)="sendOffer(t.b)">
                <div class="fw-semibold">{{ 'flex.handover_title' | translate: { ref: t.b.booking_ref } }}</div>
                <p class="small text-muted mb-2">{{ 'flex.handover_help' | translate }}</p>
                <label class="form-label small" [for]="'he' + t.b.id">{{ 'flex.friend_email' | translate }}</label>
                <input [id]="'he' + t.b.id" type="email" class="form-control form-control-sm mb-1" formControlName="email" autocomplete="off">
                @if (fieldError('email'); as m) { <div class="text-danger small mb-1">{{ m }}</div> }
                <label class="form-label small mt-1" [for]="'hm' + t.b.id">{{ 'flex.message_optional' | translate }}</label>
                <input [id]="'hm' + t.b.id" type="text" maxlength="200" class="form-control form-control-sm mb-2" formControlName="message">
                <button class="btn btn-primary btn-sm me-2" type="submit" [disabled]="handoverForm.invalid || busy() === t.b.id">{{ 'flex.send_offer' | translate }}</button>
                <button class="btn btn-outline-secondary btn-sm" type="button" (click)="handoverFor.set(null)">{{ 'common.cancel' | translate }}</button>
              </form>
            }

            @if (timelineOpen() === t.b.id) {
              <div class="mt-3 border-top pt-2">
                @if (timelines()[t.b.id]; as tl) {
                  <ol class="list-unstyled mb-0 small">
                    @for (e of tl.events; track $index) {
                      <li class="mb-1">
                        <span class="text-muted">{{ e.at | appDate: true }}</span> —
                        <strong>{{ 'flex.event.' + e.kind | translate }}</strong>
                        <span class="badge text-bg-light border ms-1">{{ 'flex.by_' + e.by | translate }}</span>
                      </li>
                    }
                  </ol>
                } @else {
                  <div class="spinner-border spinner-border-sm" role="status"></div>
                }
              </div>
            }
          </div>
        </div>
      }
    }
  `,
})
export class ManageBookingsComponent {
  private bookings = inject(BookingsService);
  private flex = inject(FlexService);
  private language = inject(LanguageService);
  private translate = inject(TranslateService);
  private fb = inject(FormBuilder);

  trips = signal<{ b: Booking; s: FlexState }[]>([]);
  incoming = signal<IncomingHandover[]>([]);
  loading = signal(true);
  failed = signal(false);
  busy = signal<number | string | null>(null);
  flash = signal<Flash | null>(null);
  confirming = signal<{ id: number; preview: CancelPreview } | null>(null);
  handoverFor = signal<number | null>(null);
  handoverError = signal<ApiErrorBody | null>(null);
  timelineOpen = signal<number | null>(null);
  timelines = signal<Record<number, Timeline>>({});

  handoverForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    message: [''],
  });

  constructor() {
    effect(() => { this.language.lang(); untracked(() => this.load()); });
  }

  load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.flex.state().subscribe({
      next: states => {
        this.flex.incoming(this.language.lang()).subscribe({ next: i => this.incoming.set(i), error: () => this.incoming.set([]) });
        this.collect(states, 1, []);
      },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }

  /** /api/bookings/mine is paged (12 per page, newest first): walk pages until every upcoming booking is found. */
  private collect(states: FlexState[], page: number, found: Booking[]): void {
    const wanted = new Set(states.map(s => s.booking_id));
    this.bookings.mine(this.language.lang(), page).subscribe({
      next: p => {
        const all = [...found, ...p.results.filter(b => wanted.has(b.id))];
        if (all.length < wanted.size && p.next && page < 10) { this.collect(states, page + 1, all); return; }
        const byId = new Map(states.map(s => [s.booking_id, s] as const));
        this.trips.set(all.map(b => ({ b, s: byId.get(b.id)! }))
                          .sort((a, b) => a.b.start_at.localeCompare(b.b.start_at)));
        this.loading.set(false);
      },
      error: () => { this.failed.set(true); this.loading.set(false); },
    });
  }

  // ---- cancel (preview first, so the tourist knows what happens)
  askCancel(b: Booking): void {
    this.flash.set(null);
    this.busy.set(b.id);
    this.flex.preview(b.id).subscribe({
      next: p => { this.busy.set(null); this.confirming.set({ id: b.id, preview: p }); },
      error: e => { this.busy.set(null); this.fail(e); },
    });
  }
  doCancel(b: Booking): void {
    this.busy.set(b.id);
    this.flex.cancel(b.id, this.language.lang()).subscribe({
      next: () => { this.confirming.set(null); this.busy.set(null); this.ok('flex.cancel_done'); this.load(); },
      error: e => { this.confirming.set(null); this.busy.set(null); this.fail(e); this.load(); },
    });
  }
  undo(b: Booking): void {
    this.busy.set(b.id);
    this.flex.undo(b.id, this.language.lang()).subscribe({
      next: () => { this.busy.set(null); this.ok('flex.undone'); this.load(); },
      error: e => { this.busy.set(null); this.fail(e); this.load(); },
    });
  }

  // ---- seat handover
  openHandover(id: number): void { this.handoverForm.reset(); this.handoverError.set(null); this.handoverFor.set(id); this.flash.set(null); }
  sendOffer(b: Booking): void {
    if (this.handoverForm.invalid) return;
    const { email, message } = this.handoverForm.getRawValue();
    this.busy.set(b.id);
    this.handoverError.set(null);
    this.flex.offer(b.id, email, message).subscribe({
      next: () => { this.busy.set(null); this.handoverFor.set(null); this.ok('flex.offer_sent'); this.load(); },
      error: e => {
        this.busy.set(null);
        const err = toApiError(e);
        if (err.field_errors?.['email']) this.handoverError.set(err); else this.fail(e);
      },
    });
  }
  withdraw(id: number): void {
    this.busy.set('w' + id);
    this.flex.withdraw(id).subscribe({
      next: () => { this.busy.set(null); this.ok('flex.withdrawn'); this.load(); },
      error: e => { this.busy.set(null); this.fail(e); this.load(); },
    });
  }
  accept(o: IncomingHandover): void {
    this.busy.set('o' + o.id);
    this.flex.accept(o.id, this.language.lang()).subscribe({
      next: () => { this.busy.set(null); this.ok('flex.accepted', { ref: o.booking_ref }); this.load(); },
      error: e => { this.busy.set(null); this.fail(e); this.load(); },
    });
  }
  decline(o: IncomingHandover): void {
    this.busy.set('o' + o.id);
    this.flex.decline(o.id).subscribe({
      next: () => { this.busy.set(null); this.ok('flex.declined'); this.load(); },
      error: e => { this.busy.set(null); this.fail(e); this.load(); },
    });
  }

  // ---- history
  toggleTimeline(id: number): void {
    if (this.timelineOpen() === id) { this.timelineOpen.set(null); return; }
    this.timelineOpen.set(id);
    this.flex.timeline(id).subscribe({
      next: t => this.timelines.update(m => ({ ...m, [id]: t })),
      error: e => { this.timelineOpen.set(null); this.fail(e); },
    });
  }

  // ---- helpers
  fieldError(field: string): string { return fieldErrorText(this.translate, this.handoverError(), field); }
  private ok(key: string, params?: object): void { this.flash.set({ kind: 'success', text: this.translate.instant(key, params) }); }
  private fail(e: unknown): void {
    const err = toApiError(e);
    this.flash.set({ kind: 'danger', text: errorText(this.translate, err.message_key, err.message) });
  }
  badge(b: Booking): string {
    const map: Record<string, string> = { Pending: 'text-bg-warning', Confirmed: 'text-bg-success', Cancelled: 'text-bg-secondary',
                                          Completed: 'text-bg-primary' };
    return 'badge ' + (map[b.status] ?? 'text-bg-light');
  }
}
