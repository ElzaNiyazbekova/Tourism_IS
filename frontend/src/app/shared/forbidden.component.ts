import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'app-forbidden',
  imports: [RouterLink, TranslatePipe],
  template: `<div class="text-center py-5"><h1 class="h3">403</h1><p class="text-muted">{{ 'errors.forbidden' | translate }}</p>
    <a routerLink="/tours" class="btn btn-primary">{{ 'common.back_to_tours' | translate }}</a></div>`,
})
export class ForbiddenComponent {}
