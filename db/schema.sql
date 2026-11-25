--
-- PostgreSQL database dump
--

\restrict VbCzjH0df7VE49IrgwpG2z888a6R4UQMUw069e3UrmhGcRUlKaHAHAGDxVYWw9y

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bookings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bookings (
    booking_id integer NOT NULL,
    booking_ref character varying(12) NOT NULL,
    booking_date date NOT NULL,
    travel_date date NOT NULL,
    travelers_count integer NOT NULL,
    total_cost numeric(10,2) NOT NULL,
    status character varying(20) NOT NULL,
    special_request text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone,
    departure_id integer NOT NULL,
    user_id integer NOT NULL,
    CONSTRAINT ck_bookings_cost CHECK ((total_cost >= (0)::numeric)),
    CONSTRAINT ck_bookings_dates CHECK ((travel_date >= booking_date)),
    CONSTRAINT ck_bookings_status CHECK (((status)::text = ANY ((ARRAY['Pending'::character varying, 'Confirmed'::character varying, 'Cancelled'::character varying, 'Completed'::character varying, 'Expired'::character varying])::text[]))),
    CONSTRAINT ck_bookings_travelers CHECK ((travelers_count > 0))
);


--
-- Name: departures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departures (
    departure_id integer NOT NULL,
    start_at timestamp with time zone NOT NULL,
    end_at timestamp with time zone NOT NULL,
    seats_total integer NOT NULL,
    seats_available integer NOT NULL,
    guide_id integer NOT NULL,
    package_id integer NOT NULL,
    is_active boolean NOT NULL,
    CONSTRAINT ck_departures_seats CHECK (((seats_available >= 0) AND (seats_available <= seats_total))),
    CONSTRAINT ck_departures_time CHECK ((end_at > start_at)),
    CONSTRAINT ck_departures_total CHECK ((seats_total > 0))
);


--
-- Name: package_translations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.package_translations (
    translation_id integer NOT NULL,
    language_code character varying(2) NOT NULL,
    title character varying(200) NOT NULL,
    description text NOT NULL,
    package_id integer NOT NULL,
    CONSTRAINT ck_translation_lang CHECK (((language_code)::text = ANY ((ARRAY['en'::character varying, 'ru'::character varying, 'kk'::character varying])::text[])))
);


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    payment_id integer NOT NULL,
    amount numeric(10,2) NOT NULL,
    status character varying(10) NOT NULL,
    transaction_ref character varying(40) NOT NULL,
    paid_at timestamp with time zone,
    booking_id integer NOT NULL,
    CONSTRAINT ck_payments_amount CHECK ((amount >= (0)::numeric)),
    CONSTRAINT ck_payments_status CHECK (((status)::text = ANY ((ARRAY['Success'::character varying, 'Failed'::character varying])::text[])))
);


--
-- Name: tour_packages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tour_packages (
    package_id integer NOT NULL,
    base_price numeric(10,2) NOT NULL,
    duration_days integer NOT NULL,
    accommodation_included boolean NOT NULL,
    transport_included boolean NOT NULL,
    is_active boolean NOT NULL,
    destination_id integer NOT NULL,
    CONSTRAINT ck_packages_duration CHECK ((duration_days > 0)),
    CONSTRAINT ck_packages_price CHECK ((base_price >= (0)::numeric))
);


--
-- Name: analyst_booking_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analyst_booking_view AS
 SELECT p.package_id,
    COALESCE(t.title, '(no English title)'::character varying) AS package_title,
    count(b.booking_id) FILTER (WHERE ((b.status)::text = ANY ((ARRAY['Pending'::character varying, 'Confirmed'::character varying])::text[]))) AS active_bookings,
    count(b.booking_id) FILTER (WHERE ((b.status)::text = 'Completed'::text)) AS completed_bookings,
    count(b.booking_id) FILTER (WHERE ((b.status)::text = 'Cancelled'::text)) AS cancelled_bookings,
    (COALESCE(sum(pay.paid), (0)::numeric))::numeric(12,2) AS revenue
   FROM ((((public.tour_packages p
     LEFT JOIN public.package_translations t ON (((t.package_id = p.package_id) AND ((t.language_code)::text = 'en'::text))))
     LEFT JOIN public.departures d ON ((d.package_id = p.package_id)))
     LEFT JOIN public.bookings b ON ((b.departure_id = d.departure_id)))
     LEFT JOIN ( SELECT payments.booking_id,
            sum(payments.amount) AS paid
           FROM public.payments
          WHERE ((payments.status)::text = 'Success'::text)
          GROUP BY payments.booking_id) pay ON ((pay.booking_id = b.booking_id)))
  GROUP BY p.package_id, t.title;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    audit_id integer NOT NULL,
    action character varying(30) NOT NULL,
    table_name character varying(60) NOT NULL,
    record_id integer,
    old_value jsonb,
    new_value jsonb,
    created_at timestamp with time zone NOT NULL,
    user_id integer
);


--
-- Name: audit_log_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ALTER COLUMN audit_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.audit_log_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: audit_seals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_seals (
    seal_id integer NOT NULL,
    prev_hash character varying(64) NOT NULL,
    hash character varying(64) NOT NULL,
    sealed_at timestamp with time zone NOT NULL,
    audit_id integer NOT NULL
);


--
-- Name: audit_seals_seal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.audit_seals ALTER COLUMN seal_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.audit_seals_seal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id integer NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: bookings_booking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.bookings ALTER COLUMN booking_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.bookings_booking_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: departures_departure_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.departures ALTER COLUMN departure_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.departures_departure_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: destinations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.destinations (
    destination_id integer NOT NULL,
    name character varying(120) NOT NULL,
    country character varying(80) NOT NULL
);


--
-- Name: destinations_destination_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.destinations ALTER COLUMN destination_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.destinations_destination_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id integer NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: favorites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.favorites (
    favorite_id integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    package_id integer NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: favorites_favorite_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.favorites ALTER COLUMN favorite_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.favorites_favorite_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: guides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.guides (
    guide_id integer NOT NULL,
    bio text NOT NULL,
    languages_spoken character varying(40) NOT NULL,
    is_active boolean NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: guides_guide_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.guides ALTER COLUMN guide_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.guides_guide_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    notification_id integer NOT NULL,
    type character varying(30) NOT NULL,
    message_key character varying(100) NOT NULL,
    params jsonb NOT NULL,
    is_read boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    booking_id integer,
    user_id integer NOT NULL
);


--
-- Name: notifications_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.notifications ALTER COLUMN notification_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.notifications_notification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: package_translations_translation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.package_translations ALTER COLUMN translation_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.package_translations_translation_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: payments_payment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.payments ALTER COLUMN payment_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.payments_payment_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reviews (
    review_id integer NOT NULL,
    rating smallint NOT NULL,
    comment text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    user_id integer NOT NULL,
    package_id integer NOT NULL,
    CONSTRAINT ck_reviews_rating CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: reviews_review_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.reviews ALTER COLUMN review_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.reviews_review_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    role_id integer NOT NULL,
    name character varying(20) NOT NULL,
    CONSTRAINT ck_roles_name CHECK (((name)::text = ANY ((ARRAY['tourist'::character varying, 'guide'::character varying, 'manager'::character varying, 'analyst'::character varying, 'admin'::character varying])::text[])))
);


--
-- Name: roles_role_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.roles ALTER COLUMN role_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.roles_role_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: seat_transfers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seat_transfers (
    transfer_id integer NOT NULL,
    to_email character varying(254) NOT NULL,
    status character varying(10) NOT NULL,
    message character varying(200) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    resolved_at timestamp with time zone,
    booking_id integer NOT NULL,
    from_user_id integer NOT NULL,
    to_user_id integer,
    CONSTRAINT ck_transfers_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'accepted'::character varying, 'declined'::character varying, 'withdrawn'::character varying, 'expired'::character varying])::text[])))
);


--
-- Name: seat_transfers_transfer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.seat_transfers ALTER COLUMN transfer_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.seat_transfers_transfer_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: stored_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stored_files (
    file_id integer NOT NULL,
    name character varying(200) NOT NULL,
    content bytea NOT NULL,
    size integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_stored_files_size CHECK ((size >= 0))
);


--
-- Name: stored_files_file_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.stored_files ALTER COLUMN file_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.stored_files_file_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tour_packages_package_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.tour_packages ALTER COLUMN package_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.tour_packages_package_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tour_photos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tour_photos (
    photo_id integer NOT NULL,
    file character varying(200) NOT NULL,
    content_type character varying(20) NOT NULL,
    caption character varying(200) NOT NULL,
    credit character varying(300) NOT NULL,
    sort_order smallint NOT NULL,
    created_at timestamp with time zone NOT NULL,
    package_id integer NOT NULL,
    CONSTRAINT ck_tour_photos_order CHECK ((sort_order >= 0)),
    CONSTRAINT ck_tour_photos_type CHECK (((content_type)::text = ANY ((ARRAY['image/jpeg'::character varying, 'image/png'::character varying, 'image/webp'::character varying])::text[])))
);


--
-- Name: tour_photos_photo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.tour_photos ALTER COLUMN photo_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.tour_photos_photo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    email character varying(254) NOT NULL,
    password_hash character varying(128) NOT NULL,
    full_name character varying(150) NOT NULL,
    phone character varying(30) NOT NULL,
    preferred_language character varying(2) NOT NULL,
    mfa_enabled boolean NOT NULL,
    mfa_secret character varying(64) NOT NULL,
    failed_login_count smallint NOT NULL,
    locked_until timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    role_id integer NOT NULL,
    CONSTRAINT ck_users_email_format CHECK (((email)::text ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'::text)),
    CONSTRAINT ck_users_failed_login CHECK ((failed_login_count >= 0)),
    CONSTRAINT ck_users_language CHECK (((preferred_language)::text = ANY ((ARRAY['en'::character varying, 'ru'::character varying, 'kk'::character varying])::text[])))
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.users ALTER COLUMN user_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.users_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (audit_id);


--
-- Name: audit_seals audit_seals_audit_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_seals
    ADD CONSTRAINT audit_seals_audit_id_key UNIQUE (audit_id);


--
-- Name: audit_seals audit_seals_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_seals
    ADD CONSTRAINT audit_seals_hash_key UNIQUE (hash);


--
-- Name: audit_seals audit_seals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_seals
    ADD CONSTRAINT audit_seals_pkey PRIMARY KEY (seal_id);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: bookings bookings_booking_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_booking_ref_key UNIQUE (booking_ref);


--
-- Name: bookings bookings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_pkey PRIMARY KEY (booking_id);


--
-- Name: departures departures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departures
    ADD CONSTRAINT departures_pkey PRIMARY KEY (departure_id);


--
-- Name: destinations destinations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.destinations
    ADD CONSTRAINT destinations_pkey PRIMARY KEY (destination_id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: departures ex_departures_guide_no_overlap; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departures
    ADD CONSTRAINT ex_departures_guide_no_overlap EXCLUDE USING gist (guide_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (is_active);


--
-- Name: favorites favorites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favorites
    ADD CONSTRAINT favorites_pkey PRIMARY KEY (favorite_id);


--
-- Name: guides guides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guides
    ADD CONSTRAINT guides_pkey PRIMARY KEY (guide_id);


--
-- Name: guides guides_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guides
    ADD CONSTRAINT guides_user_id_key UNIQUE (user_id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (notification_id);


--
-- Name: package_translations package_translations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.package_translations
    ADD CONSTRAINT package_translations_pkey PRIMARY KEY (translation_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (payment_id);


--
-- Name: payments payments_transaction_ref_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_transaction_ref_key UNIQUE (transaction_ref);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (review_id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (role_id);


--
-- Name: seat_transfers seat_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seat_transfers
    ADD CONSTRAINT seat_transfers_pkey PRIMARY KEY (transfer_id);


--
-- Name: stored_files stored_files_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stored_files
    ADD CONSTRAINT stored_files_name_key UNIQUE (name);


--
-- Name: stored_files stored_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stored_files
    ADD CONSTRAINT stored_files_pkey PRIMARY KEY (file_id);


--
-- Name: tour_packages tour_packages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tour_packages
    ADD CONSTRAINT tour_packages_pkey PRIMARY KEY (package_id);


--
-- Name: tour_photos tour_photos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tour_photos
    ADD CONSTRAINT tour_photos_pkey PRIMARY KEY (photo_id);


--
-- Name: destinations uq_destinations_name_country; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.destinations
    ADD CONSTRAINT uq_destinations_name_country UNIQUE (name, country);


--
-- Name: favorites uq_favorites_user_package; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favorites
    ADD CONSTRAINT uq_favorites_user_package UNIQUE (user_id, package_id);


--
-- Name: reviews uq_reviews_user_package; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT uq_reviews_user_package UNIQUE (user_id, package_id);


--
-- Name: package_translations uq_translation_package_lang; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.package_translations
    ADD CONSTRAINT uq_translation_package_lang UNIQUE (package_id, language_code);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: audit_log_user_id_a1b3392d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_log_user_id_a1b3392d ON public.audit_log USING btree (user_id);


--
-- Name: audit_seals_hash_e0ba0acf_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_seals_hash_e0ba0acf_like ON public.audit_seals USING btree (hash varchar_pattern_ops);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: bookings_booking_ref_04beec59_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX bookings_booking_ref_04beec59_like ON public.bookings USING btree (booking_ref varchar_pattern_ops);


--
-- Name: departures_package_id_efede256; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX departures_package_id_efede256 ON public.departures USING btree (package_id);


--
-- Name: favorites_package_id_65a0bf59; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX favorites_package_id_65a0bf59 ON public.favorites USING btree (package_id);


--
-- Name: ix_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_created ON public.audit_log USING btree (created_at DESC);


--
-- Name: ix_audit_table_record; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_table_record ON public.audit_log USING btree (table_name, record_id);


--
-- Name: ix_audit_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_user_created ON public.audit_log USING btree (user_id, created_at DESC);


--
-- Name: ix_bookings_departure; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bookings_departure ON public.bookings USING btree (departure_id);


--
-- Name: ix_bookings_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bookings_user ON public.bookings USING btree (user_id);


--
-- Name: ix_departures_guide; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departures_guide ON public.departures USING btree (guide_id);


--
-- Name: ix_departures_start_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departures_start_at ON public.departures USING btree (start_at);


--
-- Name: ix_notifications_user_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_read ON public.notifications USING btree (user_id, is_read);


--
-- Name: ix_package_translations_fts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_package_translations_fts ON public.package_translations USING gin (to_tsvector('simple'::regconfig, (((title)::text || ' '::text) || description)));


--
-- Name: ix_packages_destination; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_packages_destination ON public.tour_packages USING btree (destination_id);


--
-- Name: ix_tour_photos_package; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tour_photos_package ON public.tour_photos USING btree (package_id, sort_order);


--
-- Name: ix_transfers_to_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transfers_to_status ON public.seat_transfers USING btree (to_email, status);


--
-- Name: notifications_booking_id_65edc4c5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_booking_id_65edc4c5 ON public.notifications USING btree (booking_id);


--
-- Name: package_translations_package_id_89111041; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX package_translations_package_id_89111041 ON public.package_translations USING btree (package_id);


--
-- Name: payments_booking_id_fa2b6c3e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX payments_booking_id_fa2b6c3e ON public.payments USING btree (booking_id);


--
-- Name: payments_transaction_ref_cadde9d5_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX payments_transaction_ref_cadde9d5_like ON public.payments USING btree (transaction_ref varchar_pattern_ops);


--
-- Name: reviews_package_id_16d464f2; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX reviews_package_id_16d464f2 ON public.reviews USING btree (package_id);


--
-- Name: reviews_user_id_c23b0903; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX reviews_user_id_c23b0903 ON public.reviews USING btree (user_id);


--
-- Name: roles_name_51259447_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX roles_name_51259447_like ON public.roles USING btree (name varchar_pattern_ops);


--
-- Name: seat_transfers_booking_id_a07b51f2; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX seat_transfers_booking_id_a07b51f2 ON public.seat_transfers USING btree (booking_id);


--
-- Name: seat_transfers_from_user_id_bdc72eb8; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX seat_transfers_from_user_id_bdc72eb8 ON public.seat_transfers USING btree (from_user_id);


--
-- Name: seat_transfers_to_user_id_d0f6dd80; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX seat_transfers_to_user_id_d0f6dd80 ON public.seat_transfers USING btree (to_user_id);


--
-- Name: stored_files_name_4a80c62c_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX stored_files_name_4a80c62c_like ON public.stored_files USING btree (name varchar_pattern_ops);


--
-- Name: tour_photos_package_id_6478252c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tour_photos_package_id_6478252c ON public.tour_photos USING btree (package_id);


--
-- Name: uq_bookings_active_user_departure; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_bookings_active_user_departure ON public.bookings USING btree (user_id, departure_id) WHERE ((status)::text = ANY ((ARRAY['Pending'::character varying, 'Confirmed'::character varying])::text[]));


--
-- Name: uq_transfers_open_per_booking; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_transfers_open_per_booking ON public.seat_transfers USING btree (booking_id) WHERE ((status)::text = 'pending'::text);


--
-- Name: users_email_0ea73cca_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_email_0ea73cca_like ON public.users USING btree (email varchar_pattern_ops);


--
-- Name: users_role_id_1900a745; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX users_role_id_1900a745 ON public.users USING btree (role_id);


--
-- Name: audit_log audit_log_user_id_a1b3392d_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_a1b3392d_fk_users_user_id FOREIGN KEY (user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: audit_seals audit_seals_audit_id_317aadcb_fk_audit_log_audit_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_seals
    ADD CONSTRAINT audit_seals_audit_id_317aadcb_fk_audit_log_audit_id FOREIGN KEY (audit_id) REFERENCES public.audit_log(audit_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: bookings bookings_departure_id_4ee7fde4_fk_departures_departure_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_departure_id_4ee7fde4_fk_departures_departure_id FOREIGN KEY (departure_id) REFERENCES public.departures(departure_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: bookings bookings_user_id_6e734b08_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_user_id_6e734b08_fk_users_user_id FOREIGN KEY (user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: departures departures_guide_id_386893ff_fk_guides_guide_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departures
    ADD CONSTRAINT departures_guide_id_386893ff_fk_guides_guide_id FOREIGN KEY (guide_id) REFERENCES public.guides(guide_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: departures departures_package_id_efede256_fk_tour_packages_package_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departures
    ADD CONSTRAINT departures_package_id_efede256_fk_tour_packages_package_id FOREIGN KEY (package_id) REFERENCES public.tour_packages(package_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: favorites favorites_package_id_65a0bf59_fk_tour_packages_package_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favorites
    ADD CONSTRAINT favorites_package_id_65a0bf59_fk_tour_packages_package_id FOREIGN KEY (package_id) REFERENCES public.tour_packages(package_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: favorites favorites_user_id_d60eb79f_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favorites
    ADD CONSTRAINT favorites_user_id_d60eb79f_fk_users_user_id FOREIGN KEY (user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: guides guides_user_id_98c2b469_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.guides
    ADD CONSTRAINT guides_user_id_98c2b469_fk_users_user_id FOREIGN KEY (user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: notifications notifications_booking_id_65edc4c5_fk_bookings_booking_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_booking_id_65edc4c5_fk_bookings_booking_id FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: notifications notifications_user_id_468e288d_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_468e288d_fk_users_user_id FOREIGN KEY (user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: package_translations package_translations_package_id_89111041_fk_tour_pack; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.package_translations
    ADD CONSTRAINT package_translations_package_id_89111041_fk_tour_pack FOREIGN KEY (package_id) REFERENCES public.tour_packages(package_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: payments payments_booking_id_fa2b6c3e_fk_bookings_booking_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_booking_id_fa2b6c3e_fk_bookings_booking_id FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: reviews reviews_package_id_16d464f2_fk_tour_packages_package_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_package_id_16d464f2_fk_tour_packages_package_id FOREIGN KEY (package_id) REFERENCES public.tour_packages(package_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: reviews reviews_user_id_c23b0903_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_user_id_c23b0903_fk_users_user_id FOREIGN KEY (user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: seat_transfers seat_transfers_booking_id_a07b51f2_fk_bookings_booking_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seat_transfers
    ADD CONSTRAINT seat_transfers_booking_id_a07b51f2_fk_bookings_booking_id FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: seat_transfers seat_transfers_from_user_id_bdc72eb8_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seat_transfers
    ADD CONSTRAINT seat_transfers_from_user_id_bdc72eb8_fk_users_user_id FOREIGN KEY (from_user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: seat_transfers seat_transfers_to_user_id_d0f6dd80_fk_users_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seat_transfers
    ADD CONSTRAINT seat_transfers_to_user_id_d0f6dd80_fk_users_user_id FOREIGN KEY (to_user_id) REFERENCES public.users(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: tour_packages tour_packages_destination_id_0ee286ff_fk_destinati; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tour_packages
    ADD CONSTRAINT tour_packages_destination_id_0ee286ff_fk_destinati FOREIGN KEY (destination_id) REFERENCES public.destinations(destination_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: tour_photos tour_photos_package_id_6478252c_fk_tour_packages_package_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tour_photos
    ADD CONSTRAINT tour_photos_package_id_6478252c_fk_tour_packages_package_id FOREIGN KEY (package_id) REFERENCES public.tour_packages(package_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: users users_role_id_1900a745_fk_roles_role_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_role_id_1900a745_fk_roles_role_id FOREIGN KEY (role_id) REFERENCES public.roles(role_id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

\unrestrict VbCzjH0df7VE49IrgwpG2z888a6R4UQMUw069e3UrmhGcRUlKaHAHAGDxVYWw9y

