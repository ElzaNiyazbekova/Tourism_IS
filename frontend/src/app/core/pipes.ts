// Dates and prices formatted per UI language (Intl API, no extra libraries).
import { Pipe, PipeTransform, inject } from '@angular/core';
import { LanguageService } from './language.service';

@Pipe({ name: 'appDate', pure: false })    // impure on purpose: re-runs when the language signal changes
export class AppDatePipe implements PipeTransform {
  private language = inject(LanguageService);
  transform(value: string | Date | null | undefined, withTime = false): string {
    if (!value) return '';
    const d = typeof value === 'string' ? new Date(value) : value;
    return new Intl.DateTimeFormat(this.language.locale, {
      dateStyle: 'medium', ...(withTime ? { timeStyle: 'short' } : {}), timeZone: 'Asia/Almaty',
    }).format(d);
  }
}

@Pipe({ name: 'appMoney', pure: false })
export class AppMoneyPipe implements PipeTransform {
  private language = inject(LanguageService);
  transform(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === '') return '';
    return new Intl.NumberFormat(this.language.locale, { style: 'currency', currency: 'KZT', maximumFractionDigits: 0 }).format(Number(value));
  }
}
