// Top bar: links, language switcher, login/logout.  Owner: Aitore
import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';
import { AuthService } from '../core/auth.service';
import { LANGUAGES, LanguageService } from '../core/language.service';
import { Lang } from '../core/models';

@Component({
  selector: 'app-navbar',
  imports: [RouterLink, RouterLinkActive, TranslatePipe],
  template: `
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
      <div class="container">
        <a class="navbar-brand" routerLink="/tours">{{ 'app.title' | translate }}</a>
        <button class="navbar-toggler" type="button" (click)="open.set(!open())" [attr.aria-label]="'nav.menu' | translate">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" [class.show]="open()">
          <ul class="navbar-nav me-auto">
            <li class="nav-item"><a class="nav-link" routerLink="/tours" routerLinkActive="active">{{ 'nav.tours' | translate }}</a></li>
            @if (auth.role() === 'tourist') {
              <li class="nav-item"><a class="nav-link" routerLink="/my-bookings" routerLinkActive="active">{{ 'nav.my_bookings' | translate }}</a></li>
            }
          </ul>

          <div class="btn-group me-3" role="group" [attr.aria-label]="'nav.language' | translate">
            @for (l of languages; track l.code) {
              <button type="button" class="btn btn-sm" [class.btn-light]="language.lang() === l.code"
                      [class.btn-outline-light]="language.lang() !== l.code" (click)="setLang(l.code)">{{ l.label }}</button>
            }
          </div>

          @if (auth.user(); as u) {
            <span class="navbar-text me-3">{{ u.full_name }}</span>
            <button class="btn btn-sm btn-outline-light" (click)="auth.logout()">{{ 'nav.logout' | translate }}</button>
          } @else {
            <a class="btn btn-sm btn-outline-light me-2" routerLink="/login">{{ 'nav.login' | translate }}</a>
            <a class="btn btn-sm btn-primary" routerLink="/register">{{ 'nav.register' | translate }}</a>
          }
        </div>
      </div>
    </nav>
  `,
})
export class NavbarComponent {
  auth = inject(AuthService);
  language = inject(LanguageService);
  languages = LANGUAGES;
  open = signal(false);

  setLang(code: Lang): void {
    this.language.set(code);
    if (this.auth.isLoggedIn()) this.auth.updateProfile({ preferred_language: code }).subscribe({ error: () => {} });
  }
}
