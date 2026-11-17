// Login screen.  Owner: Aitore.  Shows lockout / wrong-password messages from the API.
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AuthService } from '../../core/auth.service';
import { errorText, toApiError } from '../../core/api-error';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe],
  template: `
    <div class="row justify-content-center">
      <div class="col-md-5">
        <div class="card shadow-sm"><div class="card-body p-4">
          <h1 class="h4 mb-3">{{ 'auth.login_title' | translate }}</h1>
          @if (error()) { <div class="alert alert-danger" role="alert">{{ error() }}</div> }
          <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
            <div class="mb-3">
              <label class="form-label" for="email">{{ 'auth.email' | translate }}</label>
              <input id="email" type="email" class="form-control" formControlName="email" autocomplete="username">
            </div>
            <div class="mb-3">
              <label class="form-label" for="password">{{ 'auth.password' | translate }}</label>
              <input id="password" type="password" class="form-control" formControlName="password" autocomplete="current-password">
            </div>
            <button class="btn btn-primary w-100" type="submit" [disabled]="form.invalid || loading()">
              @if (loading()) { <span class="spinner-border spinner-border-sm me-2"></span> }
              {{ 'auth.login_button' | translate }}
            </button>
          </form>
          <p class="mt-3 mb-0 small">{{ 'auth.no_account' | translate }} <a routerLink="/register">{{ 'nav.register' | translate }}</a></p>
        </div></div>
      </div>
    </div>
  `,
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private translate = inject(TranslateService);

  loading = signal(false);
  error = signal('');
  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: () => this.router.navigateByUrl(this.route.snapshot.queryParamMap.get('returnUrl') || '/tours'),
      error: e => {
        const err = toApiError(e);
        this.error.set(errorText(this.translate, err.message_key, err.message));
        this.loading.set(false);
      },
    });
  }
}
