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
export interface Review { id: number; rating: number; comment: string; author: string; created_at: string; }
export interface Tour {
  id: number; title: string; description: string; destination: Destination;
  base_price: string;                      // DECIMAL arrives as a string, e.g. "15000.00"
  duration_days: number; accommodation_included: boolean; transport_included: boolean;
  next_departure_at: string | null; avg_rating: number | null; review_count: number;
}
export interface TourDetail extends Tour { departures: Departure[]; reviews: Review[]; }

export interface Booking {
  id: number; booking_ref: string; package_id: number; package_title: string; start_at: string; guide_name: string;
  booking_date: string; travel_date: string; travelers_count: number; total_cost: string;
  status: 'Pending' | 'Confirmed' | 'Cancelled' | 'Completed' | 'Needs review';
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
