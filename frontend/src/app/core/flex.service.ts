// FlexBook API wrappers + response shapes (cancel / undo / handover / timeline / audit integrity).
// Kept in its own file so models.ts and api.services.ts stay untouched.  Owner: Amina A.
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Booking, Lang } from './models';

export interface FlexState {
  booking_id: number;
  can_cancel: boolean; cancel_deadline: string;
  can_undo: boolean; undo_until: string | null;
  can_handover: boolean;
  handover: { id: number; to_email: string; expires_at: string } | null;
}
export interface CancelPreview {
  allowed: boolean; reason_key: string | null; deadline: string;
  seats_returned: number; was_paid: boolean; undo_minutes: number; handover_possible: boolean;
}
export interface CancelResult { message_key: string; undo_until: string; booking: Booking; }
export interface IncomingHandover {
  id: number; from_name: string; message: string; booking_ref: string; package_id: number; package_title: string;
  start_at: string; travelers_count: number; total_cost: string; booking_status: string; expires_at: string;
}
export type TimelineKind =
  'created' | 'payment_failed' | 'confirmed' | 'completed' | 'needs_review' | 'status_changed' | 'cancelled' |
  'cancel_undone' | 'expired' | 'handover_offered' | 'handed_over' | 'handover_declined' | 'handover_withdrawn' |
  'handover_expired' | 'other';
export interface TimelineEvent { at: string; kind: TimelineKind; by: 'you' | 'system' | 'staff' | 'other'; details: Record<string, unknown>; }
export interface Timeline { booking_id: number; booking_ref: string; events: TimelineEvent[]; }
export interface AuditIntegrity {
  status: 'intact' | 'broken' | 'incomplete';
  total_rows: number; sealed_rows: number; unsealed_rows: number;
  first_break: { audit_id: number; reason: 'chain_link' | 'row_modified' } | null;
  head_hash: string | null; checked_at: string;
}

@Injectable({ providedIn: 'root' })
export class FlexService {
  private http = inject(HttpClient);

  state(): Observable<FlexState[]> { return this.http.get<FlexState[]>('/api/bookings/flex-state'); }
  preview(id: number): Observable<CancelPreview> { return this.http.get<CancelPreview>(`/api/bookings/${id}/cancel-preview`); }
  cancel(id: number, lang: Lang): Observable<CancelResult> { return this.http.post<CancelResult>(`/api/bookings/${id}/cancel`, {}, { params: { lang } }); }
  undo(id: number, lang: Lang): Observable<{ booking: Booking }> { return this.http.post<{ booking: Booking }>(`/api/bookings/${id}/undo-cancel`, {}, { params: { lang } }); }
  timeline(id: number): Observable<Timeline> { return this.http.get<Timeline>(`/api/bookings/${id}/timeline`); }
  offer(id: number, email: string, message: string): Observable<{ id: number; expires_at: string }> {
    return this.http.post<{ id: number; expires_at: string }>(`/api/bookings/${id}/handover`, { email, message });
  }
  incoming(lang: Lang): Observable<IncomingHandover[]> { return this.http.get<IncomingHandover[]>('/api/handovers/incoming', { params: { lang } }); }
  accept(id: number, lang: Lang): Observable<{ booking: Booking }> { return this.http.post<{ booking: Booking }>(`/api/handovers/${id}/accept`, {}, { params: { lang } }); }
  decline(id: number): Observable<unknown> { return this.http.post(`/api/handovers/${id}/decline`, {}); }
  withdraw(id: number): Observable<unknown> { return this.http.post(`/api/handovers/${id}/withdraw`, {}); }
  integrity(): Observable<AuditIntegrity> { return this.http.get<AuditIntegrity>('/api/admin/audit-log/integrity'); }
}
