// The ONLY file that reads process.env.
require('dotenv').config();
const server = process.env.FRIDAY_SERVER ?? 'ws://127.0.0.1:8000';

export const config = {
  wsUrl: `${server}/ws`,                    // WebSocket endpoint on the Python server
  httpUrl: server.replace(/^ws/, 'http'),   // ws:// -> http://, for GET /info
};