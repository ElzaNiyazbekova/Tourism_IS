// Thin HTTP wrappers.  Owner: Aitore
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Booking, Destination, Lang, Page, TourDetail, Tour } from './models';

@Injectable({ providedIn: 'root' })
export class ToursService {
  private http = inject(HttpClient);

  destinations(): Observable<Page<Destination>> { return this.http.get<Page<Destination>>('/api/destinations'); }

  list(filters: Record<string, string | number | null | undefined>, lang: Lang, page: number): Observable<Page<Tour>> {
    let params = new HttpParams().set('lang', lang).set('page', page);
    for (const [k, v] of Object.entries(filters)) if (v !== null && v !== undefined && v !== '') params = params.set(k, String(v));
    return this.http.get<Page<Tour>>('/api/tours', { params });
  }

  detail(id: number, lang: Lang): Observable<TourDetail> {
    return this.http.get<TourDetail>(`/api/tours/${id}`, { params: { lang } });
  }
}

@Injectable({ providedIn: 'root' })
export class BookingsService {
  private http = inject(HttpClient);

  create(body: { departure: number; travelers_count: number; special_request: string }, lang: Lang): Observable<Booking> {
    return this.http.post<Booking>('/api/bookings', body, { params: { lang } });
  }
  mine(lang: Lang, page: number): Observable<Page<Booking>> {
    return this.http.get<Page<Booking>>('/api/bookings/mine', { params: { lang, page } });
  }
}
