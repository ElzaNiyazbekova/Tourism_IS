// Admin: photos of one tour - upload (several at once), caption, order / cover, delete.  Owner: Aitore
// Embedded in the tour edit form. The server re-checks everything (type by content, 5 MB, max 10, staff only).
import { Component, OnInit, inject, input, signal } from '@angular/core';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { concatMap, from, finalize } from 'rxjs';
import { AdminService } from '../../core/api.services';
import { AdminPhoto, ApiErrorBody } from '../../core/models';
import { errorText, toApiError } from '../../core/api-error';

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_PHOTOS = 10;
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];

@Component({
  selector: 'app-admin-tour-photos',
  imports: [TranslatePipe],
  template: `
    <section class="bg-white border rounded p-3 mt-4" style="max-width: 720px">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="h5 mb-0">{{ 'admin.photos' | translate }} <span class="text-muted small">({{ photos().length }}/{{ max }})</span></h2>
        <label class="btn btn-sm btn-primary mb-0" [class.disabled]="uploading() || photos().length >= max">
          @if (uploading()) { <span class="spinner-border spinner-border-sm me-1"></span> }
          {{ 'admin.photo_upload' | translate }}
          <input type="file" class="d-none" accept="image/jpeg,image/png,image/webp" multiple
                 [disabled]="uploading() || photos().length >= max" (change)="onFiles($event)">
        </label>
      </div>
      <p class="small text-muted">{{ 'admin.photos_hint' | translate }}</p>

      @for (e of errors(); track $index) { <div class="alert alert-danger py-2 small mb-2" role="alert">{{ e }}</div> }

      @if (loading()) {
        <div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div></div>
      } @else if (photos().length === 0) {
        <p class="text-muted mb-0">{{ 'admin.no_photos' | translate }}</p>
      } @else {
        <div class="row g-3">
          @for (p of photos(); track p.id; let i = $index; let first = $first; let last = $last) {
            <div class="col-sm-6 col-md-4">
              <div class="border rounded h-100 d-flex flex-column">
                <div class="position-relative">
                  <img [src]="p.url" class="admin-photo" [alt]="p.caption" loading="lazy">
                  @if (first) { <span class="badge text-bg-primary position-absolute top-0 start-0 m-1">{{ 'admin.photo_cover' | translate }}</span> }
                </div>
                <div class="p-2 d-flex flex-column gap-2 flex-grow-1">
                  <input class="form-control form-control-sm" maxlength="200" [value]="p.caption"
                         [placeholder]="'admin.photo_caption' | translate" [attr.aria-label]="'admin.photo_caption' | translate"
                         (change)="saveCaption(p, $any($event.target).value)">
                  @if (p.credit) { <div class="small text-muted text-truncate" [title]="p.credit">{{ p.credit }}</div> }
                  <div class="d-flex gap-1 mt-auto">
                    <button type="button" class="btn btn-sm btn-outline-secondary" [disabled]="first || busy()" (click)="move(i, -1)"
                            [attr.aria-label]="'admin.photo_left' | translate" [title]="'admin.photo_left' | translate">←</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" [disabled]="last || busy()" (click)="move(i, 1)"
                            [attr.aria-label]="'admin.photo_right' | translate" [title]="'admin.photo_right' | translate">→</button>
                    @if (!first) {
                      <button type="button" class="btn btn-sm btn-outline-primary" [disabled]="busy()" (click)="makeCover(i)">{{ 'admin.photo_make_cover' | translate }}</button>
                    }
                    @if (confirmId() === p.id) {
                      <button type="button" class="btn btn-sm btn-danger ms-auto" [disabled]="busy()" (click)="remove(p)">{{ 'admin.photo_delete_yes' | translate }}</button>
                    } @else {
                      <button type="button" class="btn btn-sm btn-outline-danger ms-auto" [disabled]="busy()" (click)="confirmId.set(p.id)"
                              [attr.aria-label]="'admin.photo_delete' | translate" [title]="'admin.photo_delete' | translate">✕</button>
                    }
                  </div>
                </div>
              </div>
            </div>
          }
        </div>
      }
    </section>
  `,
})
export class AdminTourPhotosComponent implements OnInit {
  readonly tourId = input.required<number>();
  readonly max = MAX_PHOTOS;

  private api = inject(AdminService);
  private translate = inject(TranslateService);

  photos = signal<AdminPhoto[]>([]);
  loading = signal(true);
  uploading = signal(false);
  busy = signal(false);
  errors = signal<string[]>([]);
  confirmId = signal<number | null>(null);

  ngOnInit(): void {
    this.api.photos(this.tourId()).subscribe({
      next: p => { this.photos.set(p); this.loading.set(false); },
      error: e => { this.fail(toApiError(e)); this.loading.set(false); },
    });
  }

  onFiles(ev: Event): void {
    const inputEl = ev.target as HTMLInputElement;
    const files = Array.from(inputEl.files ?? []);
    inputEl.value = '';                                  // allow choosing the same file again
    this.errors.set([]);
    const room = MAX_PHOTOS - this.photos().length;
    const ok: File[] = [];
    for (const f of files) {                             // quick checks for a friendly message; the server decides
      if (!TYPES.includes(f.type)) this.addError(this.t('errors.photo.bad_type'), f.name);
      else if (f.size > MAX_BYTES) this.addError(this.t('errors.photo.too_large'), f.name);
      else if (ok.length >= room) this.addError(this.t('errors.photo.too_many'), f.name);
      else ok.push(f);
    }
    if (!ok.length) return;
    this.uploading.set(true);
    from(ok).pipe(
      concatMap(f => this.api.uploadPhoto(this.tourId(), f)),     // one by one keeps the order the user picked
      finalize(() => this.uploading.set(false)),
    ).subscribe({
      next: p => this.photos.update(list => [...list, p]),
      error: e => this.fail(toApiError(e)),
    });
  }

  saveCaption(p: AdminPhoto, caption: string): void {
    if (caption === p.caption) return;
    this.api.updatePhoto(p.id, { caption }).subscribe({
      next: saved => this.photos.update(list => list.map(x => x.id === saved.id ? saved : x)),
      error: e => this.fail(toApiError(e)),
    });
  }

  move(i: number, dir: number): void {
    const ids = this.photos().map(p => p.id);
    [ids[i], ids[i + dir]] = [ids[i + dir], ids[i]];
    this.saveOrder(ids);
  }

  makeCover(i: number): void {
    const ids = this.photos().map(p => p.id);
    this.saveOrder([ids[i], ...ids.filter((_, k) => k !== i)]);
  }

  remove(p: AdminPhoto): void {
    this.busy.set(true);
    this.api.deletePhoto(p.id).pipe(finalize(() => { this.busy.set(false); this.confirmId.set(null); })).subscribe({
      next: () => this.photos.update(list => list.filter(x => x.id !== p.id)),
      error: e => this.fail(toApiError(e)),
    });
  }

  private saveOrder(ids: number[]): void {
    this.busy.set(true);
    this.errors.set([]);
    this.api.reorderPhotos(this.tourId(), ids).pipe(finalize(() => this.busy.set(false))).subscribe({
      next: list => this.photos.set(list),
      error: e => this.fail(toApiError(e)),
    });
  }

  private t(key: string): string { return this.translate.instant(key); }
  private addError(msg: string, name?: string): void { this.errors.update(l => [...l, name ? `${name}: ${msg}` : msg]); }
  private fail(e: ApiErrorBody): void { this.addError(errorText(this.translate, e.message_key, e.message)); }
}
