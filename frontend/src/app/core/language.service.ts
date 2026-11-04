// Runtime language switching (EN / RU / KZ).  Owner: Amina S. (translation keys) / Amina A.
// Choice is saved in localStorage here and in the user profile by the navbar (PATCH /api/me).
import { Injectable, inject, signal } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { Lang } from './models';

export const LANGUAGES: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' }, { code: 'ru', label: 'Русский' }, { code: 'kk', label: 'Қазақша' },
];
const LOCALES: Record<Lang, string> = { en: 'en-GB', ru: 'ru-RU', kk: 'kk-KZ' };

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private translate = inject(TranslateService);
  readonly lang = signal<Lang>('en');

  init(): void {
    let saved: string | null = null;
    try { saved = localStorage.getItem('lang'); } catch { /* storage blocked: stay on English */ }
    this.set(LANGUAGES.some(l => l.code === saved) ? (saved as Lang) : 'en');
  }

  set(lang: Lang): void {
    this.lang.set(lang);
    this.translate.use(lang);
    document.documentElement.lang = lang;
    try { localStorage.setItem('lang', lang); } catch { /* ignore */ }
  }

  get locale(): string { return LOCALES[this.lang()]; }
}
