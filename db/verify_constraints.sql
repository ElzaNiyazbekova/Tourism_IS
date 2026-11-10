-- =====================================================================
-- Proves that the DATABASE ITSELF rejects bad data (no application code involved).
-- Owner: Elza (Data & Database) / Dastan (Testing).
--
-- Works on BOTH ways of building the schema (every INSERT lists all columns, so it does not depend on defaults):
--   A) the hand-written script:   createdb scratch && psql -d scratch -f db/create_tables.sql -f db/verify_constraints.sql
--   B) the Django-built schema:   (after `python manage.py migrate` on an EMPTY database)  psql -d tourism -f db/verify_constraints.sql
-- Everything runs inside one transaction that is rolled back at the end, so the database stays empty.
--
-- Each check says WHICH kind of error it expects (SQLSTATE). A statement that fails for another reason
-- (for example a forgotten NOT NULL column) is reported as FAIL, so a "PASS" really means the intended rule fired.
--   23P01 exclusion constraint   23505 unique   23514 check   23503 foreign key / RESTRICT   23502 not null
-- Last line of output: "22 PASS, 0 FAIL"
-- =====================================================================
\set QUIET on
\pset footer off
BEGIN;
-- Django creates foreign keys as DEFERRABLE INITIALLY DEFERRED; check them at once so each test sees its own error
SET CONSTRAINTS ALL IMMEDIATE;

CREATE TEMP TABLE _results (rule TEXT, outcome TEXT);

CREATE FUNCTION pg_temp.expect_fail(rule TEXT, stmt TEXT, expected TEXT) RETURNS void AS $$
BEGIN
    BEGIN
        EXECUTE stmt;
        INSERT INTO _results VALUES (rule, 'FAIL - statement was accepted');
        RAISE EXCEPTION 'undo' USING ERRCODE = 'P0001';   -- undo the wrongly accepted row
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'undo' AND SQLSTATE = 'P0001' THEN NULL;
        ELSIF SQLSTATE = expected THEN
            INSERT INTO _results VALUES (rule, 'PASS - ' || split_part(SQLERRM, E'\n', 1));
        ELSE
            INSERT INTO _results VALUES (rule, 'FAIL - rejected for another reason (' || SQLSTATE || '): ' || split_part(SQLERRM, E'\n', 1));
        END IF;
    END;
END $$ LANGUAGE plpgsql;

-- ---- base data (one tourist, one guide, one tour, one departure, one booking) ----
INSERT INTO roles (name) VALUES ('tourist'), ('guide') ON CONFLICT (name) DO NOTHING;
INSERT INTO users (email, password_hash, full_name, phone, role_id, preferred_language, mfa_enabled, mfa_secret, failed_login_count, created_at)
  SELECT 't1@example.com', 'x', 'Tourist One', '', role_id, 'en', FALSE, '', 0, now() FROM roles WHERE name = 'tourist';
INSERT INTO users (email, password_hash, full_name, phone, role_id, preferred_language, mfa_enabled, mfa_secret, failed_login_count, created_at)
  SELECT 'g1@example.com', 'x', 'Guide One', '', role_id, 'en', FALSE, '', 0, now() FROM roles WHERE name = 'guide';
INSERT INTO guides (user_id, bio, languages_spoken, is_active) SELECT user_id, '', 'en', TRUE FROM users WHERE email = 'g1@example.com';
INSERT INTO destinations (name, country) VALUES ('Almaty', 'Kazakhstan');
INSERT INTO tour_packages (destination_id, base_price, duration_days, accommodation_included, transport_included, is_active)
  SELECT destination_id, 15000, 1, FALSE, FALSE, TRUE FROM destinations;
INSERT INTO departures (package_id, guide_id, start_at, end_at, seats_total, seats_available, is_active)
  SELECT p.package_id, g.guide_id, '2027-01-10 09:00+05', '2027-01-10 17:00+05', 5, 5, TRUE FROM tour_packages p, guides g;
INSERT INTO bookings (booking_ref, user_id, departure_id, booking_date, travel_date, travelers_count, total_cost, status, special_request, created_at)
  SELECT 'BK-0001', u.user_id, d.departure_id, '2026-11-04', '2027-01-10', 2, 30000, 'Pending', '', now()
  FROM users u, departures d WHERE u.email = 't1@example.com';

\o /dev/null
-- ---- the 22 checks ---------------------------------------------------------------
-- 1
SELECT pg_temp.expect_fail('BR-01 overlapping guide slot',
 $s$INSERT INTO departures (package_id, guide_id, start_at, end_at, seats_total, seats_available, is_active)
    SELECT package_id, guide_id, '2027-01-10 12:00+05', '2027-01-10 20:00+05', 3, 3, TRUE FROM departures$s$, '23P01');
-- 2
SELECT pg_temp.expect_fail('duplicate user email',
 $s$INSERT INTO users (email, password_hash, full_name, phone, role_id, preferred_language, mfa_enabled, mfa_secret, failed_login_count, created_at)
    SELECT 't1@example.com', 'x', 'Dup', '', role_id, 'en', FALSE, '', 0, now() FROM roles LIMIT 1$s$, '23505');
-- 3
SELECT pg_temp.expect_fail('invalid email format',
 $s$INSERT INTO users (email, password_hash, full_name, phone, role_id, preferred_language, mfa_enabled, mfa_secret, failed_login_count, created_at)
    SELECT 'not-an-email', 'x', 'Bad', '', role_id, 'en', FALSE, '', 0, now() FROM roles LIMIT 1$s$, '23514');
-- 4
SELECT pg_temp.expect_fail('missing email (NULL)',
 $s$INSERT INTO users (email, password_hash, full_name, phone, role_id, preferred_language, mfa_enabled, mfa_secret, failed_login_count, created_at)
    SELECT NULL, 'x', 'NoMail', '', role_id, 'en', FALSE, '', 0, now() FROM roles LIMIT 1$s$, '23502');
-- 5
SELECT pg_temp.expect_fail('duplicate ACTIVE booking (same user + departure)',
 $s$INSERT INTO bookings (booking_ref, user_id, departure_id, booking_date, travel_date, travelers_count, total_cost, status, special_request, created_at)
    SELECT 'BK-0002', user_id, departure_id, '2026-11-04', '2027-01-10', 1, 15000, 'Confirmed', '', now() FROM bookings$s$, '23505');
-- 6
SELECT pg_temp.expect_fail('travel_date before booking_date',
 $s$INSERT INTO bookings (booking_ref, user_id, departure_id, booking_date, travel_date, travelers_count, total_cost, status, special_request, created_at)
    SELECT 'BK-0003', user_id, departure_id, '2026-11-04', '2026-11-01', 1, 1, 'Cancelled', '', now() FROM bookings$s$, '23514');
-- 7
SELECT pg_temp.expect_fail('travelers_count = 0', $s$UPDATE bookings SET travelers_count = 0$s$, '23514');
-- 8
SELECT pg_temp.expect_fail('negative total_cost', $s$UPDATE bookings SET total_cost = -1$s$, '23514');
-- 9
SELECT pg_temp.expect_fail('invalid status "Maybe"', $s$UPDATE bookings SET status = 'Maybe'$s$, '23514');
-- 10
SELECT pg_temp.expect_fail('booking without existing user (FK)',
 $s$INSERT INTO bookings (booking_ref, user_id, departure_id, booking_date, travel_date, travelers_count, total_cost, status, special_request, created_at)
    SELECT 'BK-0004', 99999, departure_id, '2026-11-04', '2027-01-10', 1, 1, 'Cancelled', '', now() FROM departures$s$, '23503');
-- 11
SELECT pg_temp.expect_fail('booking without existing departure (FK)',
 $s$INSERT INTO bookings (booking_ref, user_id, departure_id, booking_date, travel_date, travelers_count, total_cost, status, special_request, created_at)
    SELECT 'BK-0005', user_id, 99999, '2026-11-04', '2027-01-10', 1, 1, 'Cancelled', '', now() FROM users LIMIT 1$s$, '23503');
-- 12
SELECT pg_temp.expect_fail('duplicate booking_ref',
 $s$INSERT INTO bookings (booking_ref, user_id, departure_id, booking_date, travel_date, travelers_count, total_cost, status, special_request, created_at)
    SELECT 'BK-0001', user_id, departure_id, '2026-11-04', '2027-01-10', 1, 1, 'Cancelled', '', now() FROM bookings$s$, '23505');
-- 13
SELECT pg_temp.expect_fail('delete user that has bookings (RESTRICT)', $s$DELETE FROM users WHERE email = 't1@example.com'$s$, '23503');
-- 14
SELECT pg_temp.expect_fail('delete package that has departures (RESTRICT)', $s$DELETE FROM tour_packages$s$, '23503');
-- 15
SELECT pg_temp.expect_fail('seats_available above seats_total', $s$UPDATE departures SET seats_available = seats_total + 1$s$, '23514');
-- 16
SELECT pg_temp.expect_fail('seats_available below zero', $s$UPDATE departures SET seats_available = -1$s$, '23514');
-- 17
SELECT pg_temp.expect_fail('end_at before start_at', $s$UPDATE departures SET end_at = start_at - interval '1 hour'$s$, '23514');
-- 18
SELECT pg_temp.expect_fail('negative base_price', $s$UPDATE tour_packages SET base_price = -5$s$, '23514');
-- 19
SELECT pg_temp.expect_fail('duration_days = 0', $s$UPDATE tour_packages SET duration_days = 0$s$, '23514');
-- 20
SELECT pg_temp.expect_fail('rating 6',
 $s$INSERT INTO reviews (user_id, package_id, rating, comment, created_at)
    SELECT u.user_id, p.package_id, 6, '', now() FROM users u, tour_packages p LIMIT 1$s$, '23514');
-- 21
SELECT pg_temp.expect_fail('duplicate translation (package + language)',
 $s$INSERT INTO package_translations (package_id, language_code, title, description) SELECT package_id, 'en', 'A', '' FROM tour_packages;
    INSERT INTO package_translations (package_id, language_code, title, description) SELECT package_id, 'en', 'B', '' FROM tour_packages$s$, '23505');
\o

-- 22: a legal, back-to-back slot (17:00 right after 17:00) must still be ACCEPTED ('[)' ranges)
DO $$ BEGIN
    INSERT INTO departures (package_id, guide_id, start_at, end_at, seats_total, seats_available, is_active)
    SELECT package_id, guide_id, '2027-01-10 17:00+05', '2027-01-10 20:00+05', 3, 3, TRUE FROM departures LIMIT 1;
    INSERT INTO _results VALUES ('back-to-back slot (17:00 right after 17:00) is allowed', 'PASS - accepted as expected');
EXCEPTION WHEN OTHERS THEN
    INSERT INTO _results VALUES ('back-to-back slot is allowed', 'FAIL - ' || SQLERRM);
END $$;

\pset format aligned
SELECT rule, outcome FROM _results ORDER BY (outcome LIKE 'FAIL%') DESC, rule;
SELECT COUNT(*) FILTER (WHERE outcome LIKE 'PASS%') || ' PASS, ' ||
       COUNT(*) FILTER (WHERE outcome LIKE 'FAIL%') || ' FAIL' AS "RESULT" FROM _results;
ROLLBACK;
