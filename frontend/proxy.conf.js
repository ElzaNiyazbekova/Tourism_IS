// Dev server proxy: the browser talks to :4200 only, /api goes to Django (no CORS pain). Owner: Amina A.
const target = process.env.BACKEND_URL || 'http://localhost:8000';
module.exports = {
  '/api': { target, secure: false, changeOrigin: true },
  '/health': { target, secure: false, changeOrigin: true },
};
