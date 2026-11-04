# ER diagram (Mermaid)  - Owner: Elza (Data & Database) / Amina S. (slide)

> On the ER slide the `USERS` entity is labelled **"CUSTOMERS / users"** (tourists are users with role = tourist).
> 12 entities, PK/FK marked. All foreign keys are `ON DELETE RESTRICT` (deactivate, never delete).

```mermaid
erDiagram
    ROLES ||--o{ USERS : "has"
    USERS ||--o| GUIDES : "is a"
    DESTINATIONS ||--o{ TOUR_PACKAGES : "contains"
    TOUR_PACKAGES ||--o{ PACKAGE_TRANSLATIONS : "has texts in"
    TOUR_PACKAGES ||--o{ DEPARTURES : "is offered as"
    GUIDES ||--o{ DEPARTURES : "leads"
    USERS ||--o{ BOOKINGS : "makes"
    DEPARTURES ||--o{ BOOKINGS : "is booked in"
    BOOKINGS ||--o{ PAYMENTS : "is paid by"
    USERS ||--o{ REVIEWS : "writes"
    TOUR_PACKAGES ||--o{ REVIEWS : "receives"
    USERS ||--o{ NOTIFICATIONS : "receives"
    BOOKINGS |o--o{ NOTIFICATIONS : "about"
    USERS |o--o{ AUDIT_LOG : "causes"

    ROLES { int role_id PK
            string name UK }
    USERS { int user_id PK
            string email UK
            string password_hash
            string full_name
            string phone
            int role_id FK
            string preferred_language
            bool mfa_enabled
            int failed_login_count
            datetime locked_until
            datetime created_at }
    GUIDES { int guide_id PK
             int user_id FK "unique"
             text bio
             string languages_spoken
             bool is_active }
    DESTINATIONS { int destination_id PK
                   string name
                   string country }
    TOUR_PACKAGES { int package_id PK
                    int destination_id FK
                    decimal base_price "CHECK >= 0"
                    int duration_days "CHECK > 0"
                    bool accommodation_included
                    bool transport_included
                    bool is_active }
    PACKAGE_TRANSLATIONS { int translation_id PK
                           int package_id FK
                           string language_code "UNIQUE with package_id"
                           string title
                           text description }
    DEPARTURES { int departure_id PK
                 int package_id FK
                 int guide_id FK "EXCLUDE overlap per guide"
                 datetime start_at
                 datetime end_at "CHECK > start_at"
                 int seats_total
                 int seats_available "CHECK 0..seats_total" }
    BOOKINGS { int booking_id PK
               string booking_ref UK "BK-0001"
               int user_id FK
               int departure_id FK
               date booking_date
               date travel_date "CHECK >= booking_date"
               int travelers_count "CHECK > 0"
               decimal total_cost "frozen"
               string status "5 allowed values"
               text special_request
               datetime created_at
               datetime expires_at }
    PAYMENTS { int payment_id PK
               int booking_id FK
               decimal amount
               string status
               string transaction_ref UK
               datetime paid_at }
    REVIEWS { int review_id PK
              int user_id FK
              int package_id FK
              int rating "1..5"
              text comment }
    NOTIFICATIONS { int notification_id PK
                    int user_id FK
                    int booking_id FK "nullable"
                    string type
                    string message_key
                    json params
                    bool is_read }
    AUDIT_LOG { int audit_id PK
                int user_id FK "null = system"
                string action
                string table_name
                int record_id
                json old_value
                json new_value
                datetime created_at }
```
