-- =====================================================================
-- Proves that the database itself rejects bad data (no application code involved).
-- Owner: Elza (Data & Database) / Dastan (Testing).
-- Run on an EMPTY database right after create_tables.sql:
--   psql -d tourism -f db/create_tables.sql -f db/verify_constraints.sql
-- Everything runs inside one transaction that is rolled back at the end.
-- Output: one line per rule: PASS (statement was rejected) or FAIL (it was accepted).
-- =====================================================================
BEGIN;

CREATE TEMP TABLE _results (rule TEXT, outcome TEXT);

CREATE FUNCTION pg_temp.expect_fail(rule TEXT, stmt TEXT) RETURNS void AS $$
BEGIN
    BEGIN
        EXECUTE stmt;
        INSERT INTO _results VALUES (rule, 'FAIL - statement was accepted');
        RAISE EXCEPTION 'undo' USING ERRCODE = 'P0001';   -- undo the accepted row
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'undo' THEN NULL;
        ELSE INSERT INTO _results VALUES (rule, 'PASS - ' || split_part(SQLERRM, E'\n', 1)); END IF;
    END;
END $$ LANGUAGE plpgsql;

-- base data -----------------------------------------------------------
INSERT INTO roles (name) VALUES ('tourist'),('guide');
INSERT INTO users (email,password_hash,full_name,role_id) VALUES
  ('t1@example.com','x','Tourist One',(SELECT role_id FROM roles WHERE name='tourist')),
  ('g1@example.com','x','Guide One',  (SELECT role_id FROM roles WHERE name='guide'));
INSERT INTO guides (user_id) SELECT user_id FROM users WHERE email='g1@example.com';
INSERT INTO destinations (name,country) VALUES ('Almaty','Kazakhstan');
INSERT INTO tour_packages (destination_id,base_price,duration_days)
  SELECT destination_id, 15000, 1 FROM destinations;
INSERT INTO departures (package_id,guide_id,start_at,end_at,seats_total,seats_available)
  SELECT p.package_id, g.guide_id, '2027-01-10 09:00+05','2027-01-10 17:00+05', 5, 5
  FROM tour_packages p, guides g;
INSERT INTO bookings (booking_ref,user_id,departure_id,booking_date,travel_date,travelers_count,total_cost,status)
  SELECT 'BK-0001', u.user_id, d.departure_id, '2026-11-04','2027-01-10', 2, 30000, 'Pending'
  FROM users u, departures d WHERE u.email='t1@example.com';

\o /dev/null
-- the rules -----------------------------------------------------------
SELECT pg_temp.expect_fail('BR-01 overlapping guide slot',
 $s$INSERT INTO departures (package_id,guide_id,start_at,end_at,seats_total,seats_available)
    SELECT package_id, guide_id, '2027-01-10 12:00+05','2027-01-10 20:00+05',3,3 FROM departures$s$);
SELECT pg_temp.expect_fail('duplicate user email',
 $s$INSERT INTO users (email,password_hash,full_name,role_id) SELECT 't1@example.com','x','Dup',role_id FROM roles LIMIT 1$s$);
SELECT pg_temp.expect_fail('invalid email format',
 $s$INSERT INTO users (email,password_hash,full_name,role_id) SELECT 'not-an-email','x','Bad',role_id FROM roles LIMIT 1$s$);
SELECT pg_temp.expect_fail('missing email (NULL)',
 $s$INSERT INTO users (email,password_hash,full_name,role_id) SELECT NULL,'x','NoMail',role_id FROM roles LIMIT 1$s$);
SELECT pg_temp.expect_fail('duplicate ACTIVE booking (same user + departure)',
 $s$INSERT INTO bookings (booking_ref,user_id,departure_id,booking_date,travel_date,travelers_count,total_cost,status)
    SELECT 'BK-0002', user_id, departure_id,'2026-11-04','2027-01-10',1,15000,'Confirmed' FROM bookings$s$);
SELECT pg_temp.expect_fail('travel_date before booking_date',
 $s$INSERT INTO bookings (booking_ref,user_id,departure_id,booking_date,travel_date,travelers_count,total_cost)
    SELECT 'BK-0003', user_id, departure_id,'2026-11-04','2026-11-01',1,1 FROM bookings$s$);
SELECT pg_temp.expect_fail('travelers_count = 0',
 $s$UPDATE bookings SET travelers_count = 0$s$);
SELECT pg_temp.expect_fail('negative total_cost',
 $s$UPDATE bookings SET total_cost = -1$s$);
SELECT pg_temp.expect_fail('invalid status "Maybe"',
 $s$UPDATE bookings SET status = 'Maybe'$s$);
SELECT pg_temp.expect_fail('booking without existing user (FK)',
 $s$INSERT INTO bookings (booking_ref,user_id,departure_id,booking_date,travel_date,travelers_count,total_cost)
    SELECT 'BK-0004', 99999, departure_id,'2026-11-04','2027-01-10',1,1 FROM departures$s$);
SELECT pg_temp.expect_fail('booking without existing departure (FK)',
 $s$INSERT INTO bookings (booking_ref,user_id,departure_id,booking_date,travel_date,travelers_count,total_cost)
    SELECT 'BK-0005', user_id, 99999,'2026-11-04','2027-01-10',1,1 FROM users LIMIT 1$s$);
SELECT pg_temp.expect_fail('duplicate booking_ref',
 $s$INSERT INTO bookings (booking_ref,user_id,departure_id,booking_date,travel_date,travelers_count,total_cost,status)
    SELECT 'BK-0001', user_id, departure_id,'2026-11-04','2027-01-10',1,1,'Cancelled' FROM bookings$s$);
SELECT pg_temp.expect_fail('delete user that has bookings (RESTRICT)',
 $s$DELETE FROM users WHERE email = 't1@example.com'$s$);
SELECT pg_temp.expect_fail('delete package that has departures (RESTRICT)',
 $s$DELETE FROM tour_packages$s$);
SELECT pg_temp.expect_fail('seats_available above seats_total',
 $s$UPDATE departures SET seats_available = seats_total + 1$s$);
SELECT pg_temp.expect_fail('seats_available below zero',
 $s$UPDATE departures SET seats_available = -1$s$);
SELECT pg_temp.expect_fail('end_at before start_at',
 $s$UPDATE departures SET end_at = start_at - interval '1 hour'$s$);
SELECT pg_temp.expect_fail('negative base_price',
 $s$UPDATE tour_packages SET base_price = -5$s$);
SELECT pg_temp.expect_fail('duration_days = 0',
 $s$UPDATE tour_packages SET duration_days = 0$s$);
SELECT pg_temp.expect_fail('rating 6',
 $s$INSERT INTO reviews (user_id,package_id,rating) SELECT u.user_id,p.package_id,6 FROM users u, tour_packages p LIMIT 1$s$);
SELECT pg_temp.expect_fail('duplicate translation (package + language)',
 $s$INSERT INTO package_translations (package_id,language_code,title) SELECT package_id,'en','A' FROM tour_packages;
    INSERT INTO package_translations (package_id,language_code,title) SELECT package_id,'en','B' FROM tour_packages$s$);

\o
-- a legal, back-to-back slot must still be accepted ('[)' ranges)
DO $$ BEGIN
    INSERT INTO departures (package_id,guide_id,start_at,end_at,seats_total,seats_available)
    SELECT package_id, guide_id, '2027-01-10 17:00+05','2027-01-10 20:00+05',3,3 FROM departures LIMIT 1;
    INSERT INTO _results VALUES ('back-to-back slot (17:00 right after 17:00) is allowed', 'PASS - accepted as expected');
EXCEPTION WHEN OTHERS THEN
    INSERT INTO _results VALUES ('back-to-back slot is allowed', 'FAIL - ' || SQLERRM);
END $$;

SELECT rule, outcome FROM _results ORDER BY (outcome LIKE 'FAIL%') DESC, rule;
SELECT COUNT(*) FILTER (WHERE outcome LIKE 'PASS%') AS passed,
       COUNT(*) FILTER (WHERE outcome LIKE 'FAIL%') AS failed FROM _results;
ROLLBACK;
