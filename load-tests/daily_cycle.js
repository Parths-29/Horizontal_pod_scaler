import http from 'k6/http';
import { check, sleep } from 'k6';

// ─────────────────────────────────────────────────────────────────────────────
// daily_cycle.js
// A sine-wave traffic pattern simulating a 24-hour cycle compressed into 10 mins.
// Evaluates resource efficiency (does KEDA scale down?) and predictive pre-warming.
// ─────────────────────────────────────────────────────────────────────────────

export const options = {
  discardResponseBodies: true,
  scenarios: {
    daily_sine_wave: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [
        { target: 10, duration: '1m' },   // Midnight (low traffic)
        { target: 50, duration: '2m' },   // Morning ramp
        { target: 150, duration: '2m' },  // Midday peak
        { target: 150, duration: '1m' },  // Hold peak
        { target: 50, duration: '2m' },   // Evening decline
        { target: 10, duration: '2m' },   // Night (low traffic)
      ],
    },
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:5000';

export default function () {
  const res = http.get(`${BASE_URL}/`);
  
  check(res, {
    'is status 200': (r) => r.status === 200,
  });
}
