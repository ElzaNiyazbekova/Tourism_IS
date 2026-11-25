// Heart button "save to favourites". Visitors are sent to log in first.  Owner: Aitore
import { Component, computed, inject, input } from '@angular/core';
import { Router } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { AuthService } from '../core/auth.service';
import { FavoritesService } from '../core/favorites.service';

@Component({
  selector: 'app-favorite-button',
  imports: [TranslatePipe],
  template: `
    @if (fav.available()) {
      @if (overlay()) {
        <button type="button" class="btn btn-light btn-sm rounded-circle shadow-sm fav-overlay" (click)="click($event)"
                [attr.aria-pressed]="saved()" [attr.aria-label]="(saved() ? 'favorites.remove' : 'favorites.add') | translate"
                [title]="(saved() ? 'favorites.remove' : 'favorites.add') | translate">
          <span [class.text-danger]="saved()" aria-hidden="true">{{ saved() ? '♥' : '♡' }}</span>
        </button>
      } @else {
        <button type="button" class="btn btn-sm" [class.btn-outline-danger]="saved()" [class.btn-outline-secondary]="!saved()"
                (click)="click($event)" [attr.aria-pressed]="saved()">
          <span aria-hidden="true">{{ saved() ? '♥' : '♡' }}</span>
          {{ (saved() ? 'favorites.saved' : 'favorites.add') | translate }}
        </button>
      }
    }
  `,
})
export class FavoriteButtonComponent {
  tourId = input.required<number>();
  overlay = input(false);           // round button on top of a card photo

  fav = inject(FavoritesService);
  private auth = inject(AuthService);
  private router = inject(Router);
  saved = computed(() => { this.fav.count(); return this.fav.has(this.tourId()); });

  click(e: Event): void {
    e.preventDefault();             // the card itself is a link - do not open the tour
    e.stopPropagation();
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.fav.toggle(this.tourId());
  }
}
