// Shapes returned by the API (see docs/API_CONTRACT.md). Owner: Aitore
export type Lang = 'en' | 'ru' | 'kk';

export interface User {
  id: number; email: string; full_name: string; phone: string;
  role: 'tourist' | 'guide' | 'manager' | 'analyst' | 'admin';
  preferred_language: Lang; mfa_enabled: boolean;
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[]; }

export interface Destination { id: number; name: string; country: string; }
export interface GuideBrief { id: number; full_name: string; bio: string; languages: string[]; }
export interface Departure {
  id: number; start_at: string; end_at: string; seats_total: number; seats_available: number;
  is_full: boolean; guide: GuideBrief;
}
export interface GuideDeparture {
  id: number; package_id: number; package_title: string; start_at: string; end_at: string;
  seats_total: number; seats_available: number; is_full: boolean;
}
export interface GuideProfile extends GuideBrief {
  member_since: string; completed_count: number; upcoming_departures: GuideDeparture[];
}
export interface GuideMe {
  id: number; full_name: string; email: string; bio: string; languages: Lang[]; is_active: boolean;
  upcoming_count: number; completed_count: number; travelers_upcoming: number;
}
export interface CabinetDeparture {
  id: number; package_id: number; package_title: string; destination: string; start_at: string; end_at: string;
  seats_total: number; seats_available: number; is_active: boolean; bookings_count: number; travelers_count: number;
}
export interface CabinetTraveler {
  booking_ref: string; full_name: string; phone: string; travelers_count: number; status: string; special_request: string;
}
export interface CabinetDepartureDetail extends CabinetDeparture { travelers: CabinetTraveler[]; }
export interface Review { id: number; rating: number; comment: string; author: string; mine: boolean; created_at: string; }
export interface Tour {
  id: number; title: string; description: string; destination: Destination;
  base_price: string;                      // DECIMAL arrives as a string, e.g. "15000.00"
  duration_days: number; accommodation_included: boolean; transport_included: boolean;
  next_departure_at: string | null; avg_rating: number | null; review_count: number;
  cover_photo: string | null;               // /api/photos/<id> or null
}
export interface TourPhoto { id: number; url: string; caption: string; credit: string; }
export interface AdminPhoto extends TourPhoto { sort_order: number; }
export interface TourDetail extends Tour { departures: Departure[]; reviews: Review[]; photos: TourPhoto[]; }

export interface Booking {
  id: number; booking_ref: string; package_id: number; package_title: string; start_at: string; guide_name: string;
  booking_date: string; travel_date: string; travelers_count: number; total_cost: string;
  status: 'Pending' | 'Confirmed' | 'Cancelled' | 'Completed' | 'Expired';
  special_request: string; expires_at: string | null; created_at: string;
}

export interface FieldError { message_key: string; message: string; }
export interface NextDeparture { departure_id: number; package_id: number; start_at: string; seats_available: number; }
export interface ApiErrorBody {
  code: string; message_key: string; message: string;
  field_errors: Record<string, FieldError[]>;
  next_available_departure?: NextDeparture | null;
  locked_until?: string;
}

// ---- Phase 2 ----
export interface Payment { id: number; amount: string; status: 'Success' | 'Failed' | 'Pending'; transaction_ref: string; paid_at: string | null; }
export interface BookingDetail extends Booking { payments: Payment[]; }
export interface ReviewBooking extends Booking {
  departure_id: number;
  departure_seats_available: number;
  customer_name: string;
  customer_email: string;
  payments: Payment[];
  exception_reason: string;
  suggested_status: string;
}
export interface PayResult { result: 'pay' | 'fail'; message_key: string; payment: Payment; booking: Booking; }

export interface Translation { language_code: Lang; title: string; description: string; }
export interface AdminTour {
  id: number; title: string; destination: number; destination_name: string; base_price: string; duration_days: number;
  accommodation_included: boolean; transport_included: boolean; is_active: boolean; translations: Translation[];
}
export interface AdminDeparture {
  id: number; package: number; package_title: string; guide: number; guide_name: string; start_at: string; end_at: string;
  seats_total: number; seats_available: number; booked_seats: number; is_active: boolean;
}
export interface AdminGuide { id: number; full_name: string; languages: string[]; is_active: boolean; }
export interface PackageRow {
  package_id: number; title: string; destination: string; is_active: boolean;
  active_bookings: number; completed_bookings: number; cancelled_bookings: number; revenue: string;
}
export interface PackageReport { packages: PackageRow[]; totals: Record<string, number | string>; }

export interface AuditEntry {
  id: number; created_at: string; action: string; table_name: string; record_id: number | null;
  user: { id: number; full_name: string; role: string } | null;       // null = done by the system
  old_value: Record<string, unknown> | null; new_value: Record<string, unknown> | null;
}
export interface AuditFacets { tables: string[]; actions: string[]; }

export interface AdminBookingRow { booking_ref:string; tourist_name:string; tourist_email:string; package_title:string; travel_date:string; travelers_count:number; total_cost:string; status:'Pending'|'Confirmed'|'Cancelled'|'Completed'|'Expired'; created_at:string; }

export interface AdminStats { totals:{bookings:number;revenue:string;average_booking_value:string;cancellation_expiry_rate:number;cancellation_expiry_rate_label:string}; bookings_by_status:{status:string;count:number}[]; bookings_per_month:{month:string;count:number}[]; top_packages_by_revenue:{package_id:number;title:string;revenue:string}[]; }
