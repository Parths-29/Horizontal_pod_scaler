import http from 'k6/http';
import { check, sleep } from 'k6';

// ─────────────────────────────────────────────────────────────────────────────
// sudden_spike.js
// Simulates a viral event or sudden burst. Jumps from 5 RPS to 250 RPS in 5s.
// Evaluates how many requests are dropped before the cluster scales up.
// ─────────────────────────────────────────────────────────────────────────────

export const options = {
  discardResponseBodies: true,
  scenarios: {
    viral_spike: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 1000,
      stages: [
        { target: 5, duration: '1m' },     // Baseline
        { target: 250, duration: '5s' },   // Sudden spike
        { target: 250, duration: '2m' },   // Hold the spike
        { target: 5, duration: '30s' },    // Drop back down
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
