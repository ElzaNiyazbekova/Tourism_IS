import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'app-not-found',
  imports: [RouterLink, TranslatePipe],
  template: `
    <div class="text-center py-5">
      <h1 class="display-5">404</h1>
      <p class="text-muted">{{ 'errors.not_found' | translate }}</p>
      <a class="btn btn-primary" routerLink="/tours">{{ 'common.back_to_tours' | translate }}</a>
    </div>
  `,
})
export class NotFoundComponent {}
