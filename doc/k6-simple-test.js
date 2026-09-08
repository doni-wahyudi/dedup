import http from 'k6/http';
import {check, sleep} from 'k6';

// Test configuration - Simple smoke test
export const options = {
  vus: 100,           // 100 virtual users
  duration: '30s',  // Run for 30 seconds
  thresholds: {
    http_req_duration: ['p(95)<3000'],  // 95% should be below 3s
    http_req_failed: ['rate<0.05'],      // Less than 5% errors
  },
};

// Base URL
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Test image path
const TEST_IMAGE_PATH = __ENV.TEST_IMAGE_PATH || './same.jpeg';

// Load test image
const testImage = open(TEST_IMAGE_PATH, 'b');

export default function () {
  // Face search API test
  const searchResponse = http.post(
    `${BASE_URL}/api/v1/faces/search?limit=10`,
    {
      image: http.file(testImage, 'same.jpeg', 'image/jpeg'),
    },
    {
      timeout: '10s',
    }
  );
  
  check(searchResponse, {
    'status is 200': (r) => r.status === 200,
    'response time < 3s': (r) => r.timings.duration < 3000,
    'has faces': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('faces') && Array.isArray(body.faces);
      } catch (e) {
        return false;
      }
    }
  });
  
  sleep(1);
}
