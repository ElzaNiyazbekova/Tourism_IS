-- Task 9 analytics: ACTIVE bookings per package. Owner: Elza (query) / Dastan (50-booking test)
-- LEFT JOIN with the status filter in the ON clause => packages with zero bookings still show 0.
SELECT p.package_id,
       COALESCE(t.title, '(no English title)') AS package_title,
       COUNT(b.booking_id)                      AS active_bookings
FROM tour_packages p
LEFT JOIN package_translations t ON t.package_id = p.package_id AND t.language_code = 'en'
LEFT JOIN departures d           ON d.package_id = p.package_id
LEFT JOIN bookings b             ON b.departure_id = d.departure_id
                                AND b.status IN ('Pending','Confirmed')   -- filter in ON, not WHERE
GROUP BY p.package_id, t.title
ORDER BY active_bookings DESC, p.package_id;
