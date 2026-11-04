// Registration (tourists only). Server-side password rules are shown per field.  Owner: Aitore
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AuthService } from '../../core/auth.service';
import { LanguageService } from '../../core/language.service';
import { ApiErrorBody } from '../../core/models';
import { errorText, fieldErrorText, toApiError } from '../../core/api-error';

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe],
  template: `
    <div class="row justify-content-center">
      <div class="col-md-6">
        <div class="card shadow-sm"><div class="card-body p-4">
          <h1 class="h4 mb-3">{{ 'auth.register_title' | translate }}</h1>
          @if (error()) { <div class="alert alert-danger" role="alert">{{ error() }}</div> }
          <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
            <div class="mb-3">
              <label class="form-label" for="full_name">{{ 'auth.full_name' | translate }}</label>
              <input id="full_name" class="form-control" formControlName="full_name" [class.is-invalid]="fe('full_name')">
              <div class="invalid-feedback">{{ fe('full_name') }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="email">{{ 'auth.email' | translate }}</label>
              <input id="email" type="email" class="form-control" formControlName="email" autocomplete="username" [class.is-invalid]="fe('email')">
              <div class="invalid-feedback">{{ fe('email') }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="phone">{{ 'auth.phone' | translate }}</label>
              <input id="phone" class="form-control" formControlName="phone" [class.is-invalid]="fe('phone')">
              <div class="invalid-feedback">{{ fe('phone') }}</div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="password">{{ 'auth.password' | translate }}</label>
              <input id="password" type="password" class="form-control" formControlName="password" autocomplete="new-password" [class.is-invalid]="fe('password')">
              <div class="form-text">{{ 'auth.password_hint' | translate }}</div>
              <div class="invalid-feedback d-block">{{ fe('password') }}</div>
            </div>
            <button class="btn btn-primary w-100" type="submit" [disabled]="form.invalid || loading()">
              @if (loading()) { <span class="spinner-border spinner-border-sm me-2"></span> }
              {{ 'auth.register_button' | translate }}
            </button>
          </form>
          <p class="mt-3 mb-0 small">{{ 'auth.have_account' | translate }} <a routerLink="/login">{{ 'nav.login' | translate }}</a></p>
        </div></div>
      </div>
    </div>
  `,
})
export class RegisterComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private translate = inject(TranslateService);
  private language = inject(LanguageService);

  loading = signal(false);
  error = signal('');
  apiError = signal<ApiErrorBody | null>(null);
  form = this.fb.nonNullable.group({
    full_name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    phone: [''],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  fe(field: string): string { return fieldErrorText(this.translate, this.apiError(), field); }

  submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set('');
    this.apiError.set(null);
    this.auth.register({ ...this.form.getRawValue(), preferred_language: this.language.lang() }).subscribe({
      next: () => this.router.navigateByUrl('/tours'),
      error: e => {
        const err = toApiError(e);
        this.apiError.set(err);
        this.error.set(errorText(this.translate, err.message_key, err.message));
        this.loading.set(false);
      },
    });
  }
}
