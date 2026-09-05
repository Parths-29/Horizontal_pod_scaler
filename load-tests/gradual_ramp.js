import http from 'k6/http';
import { check, sleep } from 'k6';

// ─────────────────────────────────────────────────────────────────────────────
// gradual_ramp.js
// Simulates organic traffic growth. Starts at 10 RPS and scales up over 5 mins.
// Evaluates if the reactive HPA can keep pace smoothly without dropping requests.
// ─────────────────────────────────────────────────────────────────────────────

export const options = {
  discardResponseBodies: true, // Optimise memory by discarding response bodies
  scenarios: {
    organic_growth: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [
        { target: 10, duration: '1m' },   // Warm-up
        { target: 100, duration: '3m' },  // Gradual ramp up
        { target: 100, duration: '2m' },  // Hold at peak
        { target: 10, duration: '1m' },   // Cool down
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'], // Fail if more than 1% errors
    http_req_duration: ['p(95)<500'], // 95% of requests must be below 500ms
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:5000';

export default function () {
  const res = http.get(`${BASE_URL}/`);
  
  check(res, {
    'is status 200': (r) => r.status === 200,
  });
}
