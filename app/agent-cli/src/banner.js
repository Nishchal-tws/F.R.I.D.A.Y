import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// ES modules have no __file__. This is the replacement:
const here = path.dirname(fileURLToPath(import.meta.url));

let banner = '';
let title = '';

// read banner.txt and title.txt from `here` using readFileSync (utf8).
try {
    const banner = readFileSync(path.join(here, 'banner.txt'), 'utf8');
    const title = readFileSync(path.join(here, 'title.txt'), 'utf8');
} 
catch (error) {
    console.error("Error reading title.txt or banner.txt, check those files available at ${here}", error.message);
}

export {banner, title};

export const RED = '\x1b[31m';
export const BOLD = '\x1b[1m';
export const RESET = '\x1b[0m';