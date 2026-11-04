// Turns any failed HTTP call into our {code, message_key, message, field_errors} shape and translates it.
import { HttpErrorResponse } from '@angular/common/http';
import { TranslateService } from '@ngx-translate/core';
import { ApiErrorBody } from './models';

export function toApiError(e: unknown): ApiErrorBody {
  const body = (e as HttpErrorResponse)?.error;
  if (body && typeof body === 'object' && 'message_key' in body) {
    return { field_errors: {}, ...body } as ApiErrorBody;
  }
  const offline = (e as HttpErrorResponse)?.status === 0;
  return { code: offline ? 'network' : 'error', message_key: offline ? 'errors.network' : 'errors.generic',
           message: 'Something went wrong.', field_errors: {} };
}

/** Translated text for an error; falls back to the server's English message if the key is unknown. */
export function errorText(t: TranslateService, key: string, fallback: string): string {
  const out = t.instant(key);
  return out !== key ? out : fallback;
}

/** First translated error for one form field, or ''. */
export function fieldErrorText(t: TranslateService, err: ApiErrorBody | null, field: string): string {
  const first = err?.field_errors?.[field]?.[0];
  return first ? errorText(t, first.message_key, first.message) : '';
}
