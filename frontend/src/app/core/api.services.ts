// Thin HTTP wrappers.  Owner: Aitore
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { AdminDeparture, AdminGuide, AdminTour, Booking, BookingDetail, Destination, Lang, Page, PackageReport, PayResult, TourDetail, Tour } from './models';

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
  get(id: number, lang: Lang): Observable<BookingDetail> {
    return this.http.get<BookingDetail>(`/api/bookings/${id}`, { params: { lang } });
  }
  pay(id: number, result: 'pay' | 'fail', lang: Lang): Observable<PayResult> {
    return this.http.post<PayResult>(`/api/bookings/${id}/pay`, { result }, { params: { lang } });
  }
}

@Injectable({ providedIn: 'root' })
export class AdminService {
  private http = inject(HttpClient);
  tours(lang: Lang, page: number): Observable<Page<AdminTour>> { return this.http.get<Page<AdminTour>>('/api/admin/tours', { params: { lang, page } }); }
  tour(id: number, lang: Lang): Observable<AdminTour> { return this.http.get<AdminTour>(`/api/admin/tours/${id}`, { params: { lang } }); }
  saveTour(id: number | null, body: unknown, lang: Lang): Observable<AdminTour> {
    return id ? this.http.patch<AdminTour>(`/api/admin/tours/${id}`, body, { params: { lang } })
              : this.http.post<AdminTour>('/api/admin/tours', body, { params: { lang } });
  }
  setTourActive(id: number, active: boolean): Observable<AdminTour> {
    return this.http.post<AdminTour>(`/api/admin/tours/${id}/${active ? 'activate' : 'deactivate'}`, {});
  }
  departures(lang: Lang, page: number): Observable<Page<AdminDeparture>> { return this.http.get<Page<AdminDeparture>>('/api/admin/departures', { params: { lang, page } }); }
  departure(id: number, lang: Lang): Observable<AdminDeparture> { return this.http.get<AdminDeparture>(`/api/admin/departures/${id}`, { params: { lang } }); }
  saveDeparture(id: number | null, body: unknown, lang: Lang): Observable<AdminDeparture> {
    return id ? this.http.patch<AdminDeparture>(`/api/admin/departures/${id}`, body, { params: { lang } })
              : this.http.post<AdminDeparture>('/api/admin/departures', body, { params: { lang } });
  }
  setDepartureActive(id: number, active: boolean): Observable<AdminDeparture> {
    return this.http.post<AdminDeparture>(`/api/admin/departures/${id}/${active ? 'activate' : 'deactivate'}`, {});
  }
  destinations(): Observable<Destination[]> { return this.http.get<Destination[]>('/api/admin/destinations'); }
  guides(): Observable<AdminGuide[]> { return this.http.get<AdminGuide[]>('/api/admin/guides'); }
}

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private http = inject(HttpClient);
  packages(lang: Lang): Observable<PackageReport> { return this.http.get<PackageReport>('/api/analytics/packages', { params: { lang } }); }
}
