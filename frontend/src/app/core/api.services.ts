// Thin HTTP wrappers.  Owner: Aitore
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { CabinetDeparture, CabinetDepartureDetail, GuideMe, AdminDeparture, AdminPhoto, AuditEntry, AuditFacets, AdminGuide, AdminTour, Booking, BookingDetail, Destination, GuideProfile, Lang, Page, PackageReport, PayResult, AdminBookingRow, AdminStats, Review, ReviewBooking, TourDetail, Tour } from './models';

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

  guide(id: number, lang: Lang): Observable<GuideProfile> {
    return this.http.get<GuideProfile>(`/api/guides/${id}`, { params: { lang } });
  }

  review(id: number, rating: number, comment: string): Observable<Review> {
    return this.http.post<Review>(`/api/tours/${id}/reviews`, { rating, comment });
  }

  deleteReview(id: number): Observable<void> {
    return this.http.delete<void>(`/api/reviews/${id}`);
  }
}

@Injectable({ providedIn: 'root' })
export class FavoritesApi {
  private http = inject(HttpClient);

  list(lang: Lang, page: number): Observable<Page<Tour>> {
    return this.http.get<Page<Tour>>('/api/favorites', { params: { lang, page } });
  }
}

/** Guide cabinet: role "guide" only, own data only. */
@Injectable({ providedIn: 'root' })
export class GuideCabinetService {
  private http = inject(HttpClient);

  me(): Observable<GuideMe> { return this.http.get<GuideMe>('/api/guide/me'); }
  updateMe(patch: Partial<Pick<GuideMe, 'bio' | 'languages'>>): Observable<GuideMe> {
    return this.http.patch<GuideMe>('/api/guide/me', patch);
  }
  departures(when: 'upcoming' | 'past', lang: Lang, page: number): Observable<Page<CabinetDeparture>> {
    return this.http.get<Page<CabinetDeparture>>('/api/guide/departures', { params: { when, lang, page } });
  }
  departure(id: number, lang: Lang): Observable<CabinetDepartureDetail> {
    return this.http.get<CabinetDepartureDetail>(`/api/guide/departures/${id}`, { params: { lang } });
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
  photos(tourId: number): Observable<AdminPhoto[]> { return this.http.get<AdminPhoto[]>(`/api/admin/tours/${tourId}/photos`); }
  uploadPhoto(tourId: number, file: File, caption = ''): Observable<AdminPhoto> {
    const body = new FormData();
    body.append('file', file);
    body.append('caption', caption);
    return this.http.post<AdminPhoto>(`/api/admin/tours/${tourId}/photos`, body);
  }
  reorderPhotos(tourId: number, ids: number[]): Observable<AdminPhoto[]> {
    return this.http.post<AdminPhoto[]>(`/api/admin/tours/${tourId}/photos/order`, { ids });
  }
  updatePhoto(id: number, body: { caption?: string; credit?: string }): Observable<AdminPhoto> {
    return this.http.patch<AdminPhoto>(`/api/admin/photos/${id}`, body);
  }
  deletePhoto(id: number): Observable<void> { return this.http.delete<void>(`/api/admin/photos/${id}`); }
  guides(): Observable<AdminGuide[]> { return this.http.get<AdminGuide[]>('/api/admin/guides'); }
  reviewBookings(lang: Lang, page = 1): Observable<Page<ReviewBooking>> {
    return this.http.get<Page<ReviewBooking>>('/api/admin/bookings/review', { params: { lang, page } });
  }
  fixReviewBooking(id: number, lang: Lang): Observable<ReviewBooking> {
    return this.http.post<ReviewBooking>(`/api/admin/bookings/${id}/fix`, {}, { params: { lang } });
  }
  mergeReviewBooking(id: number, targetBookingId: number, lang: Lang): Observable<ReviewBooking> {
    return this.http.post<ReviewBooking>(`/api/admin/bookings/${id}/merge`, { target_booking_id: targetBookingId }, { params: { lang } });
  }
  rejectReviewBooking(id: number, lang: Lang): Observable<ReviewBooking> {
    return this.http.post<ReviewBooking>(`/api/admin/bookings/${id}/reject`, {}, { params: { lang } });
  }
  adminBookings(params: Record<string,string|number|undefined>): Observable<Page<AdminBookingRow>> { let p=new HttpParams(); for(const [k,v] of Object.entries(params)) if(v!==undefined&&v!=='') p=p.set(k,String(v)); return this.http.get<Page<AdminBookingRow>>('/api/admin/bookings',{params:p}); }
  adminStats(params: Record<string,string|undefined>): Observable<AdminStats> { let p=new HttpParams(); for(const [k,v] of Object.entries(params)) if(v) p=p.set(k,v); return this.http.get<AdminStats>('/api/admin/stats',{params:p}); }
  reportCsv(params: Record<string,string|undefined>): Observable<Blob> { let p=new HttpParams(); for(const [k,v] of Object.entries(params)) if(v) p=p.set(k,v); return this.http.get('/api/admin/report/export',{params:p,responseType:'blob'}); }
}

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private http = inject(HttpClient);
  packages(lang: Lang): Observable<PackageReport> { return this.http.get<PackageReport>('/api/analytics/packages', { params: { lang } }); }
  export(lang: Lang): Observable<Blob> { return this.http.get('/api/analytics/export',{params:{lang},responseType:'blob'}); }
}

@Injectable({ providedIn: 'root' })
export class AuditService {
  private http = inject(HttpClient);
  list(filters: Record<string, string>, page: number): Observable<Page<AuditEntry>> {
    let params = new HttpParams().set('page', page);
    for (const [k, v] of Object.entries(filters)) if (v) params = params.set(k, v);
    return this.http.get<Page<AuditEntry>>('/api/admin/audit-log', { params });
  }
  facets(): Observable<AuditFacets> { return this.http.get<AuditFacets>('/api/admin/audit-log/facets'); }
}
