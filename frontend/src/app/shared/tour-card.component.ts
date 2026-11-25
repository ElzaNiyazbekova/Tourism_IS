// One tour card (catalogue, favourites). The heart sits next to the link, not inside it.  Owner: Aitore
import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { Tour } from '../core/models';
import { AppDatePipe, AppMoneyPipe } from '../core/pipes';
import { FavoriteButtonComponent } from './favorite-button.component';

@Component({
  selector: 'app-tour-card',
  imports: [RouterLink, TranslatePipe, AppDatePipe, AppMoneyPipe, FavoriteButtonComponent],
  host: { class: 'd-block h-100' },
  template: `
    <div class="position-relative h-100">
    @if (tour(); as t) {
    <a class="card h-100 card-hover text-body overflow-hidden" [routerLink]="['/tours', t.id]">
      @if (t.cover_photo) {
        <img [src]="t.cover_photo" class="card-img-top tour-cover" [alt]="t.title" loading="lazy">
      } @else {
        <div class="card-img-top tour-cover tour-cover-empty" aria-hidden="true">🏔</div>
      }
      <div class="card-body d-flex flex-column">
        <div class="small text-muted">{{ t.destination.name }}, {{ t.destination.country }}</div>
        <h2 class="h5 mt-1">{{ t.title }}</h2>
        <p class="small text-muted flex-grow-1">{{ t.description }}</p>
        <div class="mb-2">
          @if (t.accommodation_included) { <span class="badge text-bg-light border me-1">{{ 'tours.accommodation' | translate }}</span> }
          @if (t.transport_included) { <span class="badge text-bg-light border me-1">{{ 'tours.transport' | translate }}</span> }
          <span class="badge text-bg-light border">{{ 'common.days' | translate: { count: t.duration_days } }}</span>
        </div>
        <div class="d-flex justify-content-between align-items-end">
          <div>
            <div class="fw-bold">{{ 'tours.from_price' | translate }} {{ t.base_price | appMoney }}</div>
            <div class="small text-muted">
              @if (t.next_departure_at) { {{ 'tours.next_departure' | translate }}: {{ t.next_departure_at | appDate }} }
              @else { {{ 'tours.no_departure' | translate }} }
            </div>
          </div>
          @if (t.avg_rating !== null) { <span class="badge text-bg-warning">★ {{ t.avg_rating.toFixed(1) }} ({{ t.review_count }})</span> }
        </div>
      </div>
    </a>
      <app-favorite-button class="fav-slot" [tourId]="t.id" [overlay]="true" />
    }
    </div>
  `,
})
export class TourCardComponent {
  tour = input.required<Tour>();
}
