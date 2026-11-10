// Login screen: step 1 password, step 2 authenticator code (staff).  Owner: Aitore (screen), Amina A. (lockout 423 + MFA)
// Shows lockout / wrong-password / wrong-code messages from the API.
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AuthService, isMfaChallenge } from '../../core/auth.service';
import { errorText, toApiError } from '../../core/api-error';
import { User } from '../../core/models';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, TranslatePipe],
  template: `
    <div class="row justify-content-center">
      <div class="col-md-5">
        <div class="card shadow-sm"><div class="card-body p-4">
          @if (step() === 'password') {
            <h1 class="h4 mb-3">{{ 'auth.login_title' | translate }}</h1>
          } @else {
            <h1 class="h4 mb-2">{{ 'auth.mfa_title' | translate }}</h1>
            <p class="text-muted small">{{ 'auth.mfa_hint' | translate }}</p>
          }
          @if (error()) { <div class="alert alert-danger" role="alert">{{ error() }}</div> }

          @if (step() === 'password') {
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
          } @else {
            <form [formGroup]="mfaForm" (ngSubmit)="submitCode()" novalidate>
              <div class="mb-3">
                <label class="form-label" for="code">{{ 'auth.mfa_code' | translate }}</label>
                <input id="code" type="text" class="form-control form-control-lg text-center" formControlName="code"
                       inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="123456">
              </div>
              <button class="btn btn-primary w-100" type="submit" [disabled]="mfaForm.invalid || loading()">
                @if (loading()) { <span class="spinner-border spinner-border-sm me-2"></span> }
                {{ 'auth.mfa_button' | translate }}
              </button>
            </form>
            <button type="button" class="btn btn-link btn-sm mt-2 px-0" (click)="backToPassword()">{{ 'auth.mfa_back' | translate }}</button>
          }
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
  step = signal<'password' | 'code'>('password');
  private mfaToken = '';

  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });
  mfaForm = this.fb.nonNullable.group({
    code: ['', [Validators.required, Validators.pattern(/^\s*\d{3}\s?\d{3}\s*$/)]],
  });

  submit(): void {
    if (this.form.invalid) return;
    this.start();
    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: r => {
        if (isMfaChallenge(r)) {          // password was right: ask for the code
          this.mfaToken = r.mfa_token;
          this.mfaForm.reset();
          this.step.set('code');
          this.loading.set(false);
        } else {
          this.done(r);
        }
      },
      error: e => this.fail(e),
    });
  }

  submitCode(): void {
    if (this.mfaForm.invalid) return;
    this.start();
    this.auth.verifyMfa(this.mfaToken, this.mfaForm.getRawValue().code).subscribe({
      next: u => this.done(u),
      error: e => this.fail(e),
    });
  }

  backToPassword(): void {
    this.mfaToken = '';
    this.error.set('');
    this.step.set('password');
  }

  private start(): void { this.loading.set(true); this.error.set(''); }

  private done(user: User): void {
    const staff = ['manager', 'admin', 'analyst'].includes(user.role);
    this.router.navigateByUrl(this.route.snapshot.queryParamMap.get('returnUrl') || (staff ? '/admin' : '/tours'));
  }

  private fail(e: unknown): void {
    const err = toApiError(e);
    let text = errorText(this.translate, err.message_key, err.message);
    if (err.code === 'account_locked' && err.locked_until) {          // HTTP 423: tell the user WHEN login works again
      const time = new Date(err.locked_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      text += ' ' + this.translate.instant('errors.locked_until', { time });
    }
    if (err.code === 'mfa_token_invalid') this.backToPassword();     // the 5-minute ticket ran out
    this.error.set(text);
    this.loading.set(false);
  }
}
