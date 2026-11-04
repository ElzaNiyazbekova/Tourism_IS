import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from './shared/navbar.component';
import { LanguageService } from './core/language.service';
import { AuthService } from './core/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, NavbarComponent],
  template: `
    <app-navbar />
    <main class="container py-4">
      <router-outlet />
    </main>
  `,
})
export class App {
  constructor() {
    inject(LanguageService).init();   // pick saved language, load translations
    inject(AuthService).restoreSession();  // reload /api/me when a token is stored
  }
}
