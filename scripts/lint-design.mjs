import fs from 'fs';
import path from 'path';

const SRC_DIR = path.resolve(process.cwd(), 'src');
const ALLOWED_HEX_FILES = [
  path.resolve(SRC_DIR, 'styles', 'tokens.css'),
];

let hasErrors = false;

function scanDirectory(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      scanDirectory(fullPath);
    } else if (entry.isFile() && /\.(tsx|ts|jsx|js|css|html)$/.test(entry.name)) {
      checkFile(fullPath);
    }
  }
}

function checkFile(filePath) {
  const isAllowedHex = ALLOWED_HEX_FILES.includes(filePath);
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  lines.forEach((line, index) => {
    const lineNum = index + 1;

    // 1. Check font size < 12px: e.g. text-[10px], text-[11px], text-[9px], font-size: 10px, etc.
    const fontSizeMatch = line.match(/(?:text-\[(\d+)px\]|font-size:\s*(\d+)px)/);
    if (fontSizeMatch) {
      const size = parseInt(fontSizeMatch[1] || fontSizeMatch[2], 10);
      if (size < 12) {
        console.error(`\x1b[31m[DESIGN LINT ERROR]\x1b[0m ${filePath}:${lineNum} - Font size ${size}px is below minimum 12px allowed: "${line.trim()}"`);
        hasErrors = true;
      }
    }

    // 2. Check raw hex colors in src/ (except in tokens.css)
    if (!isAllowedHex) {
      // Matches #fff, #ffffff, #ffffff80, etc. but ignores css comments or url hashes
      const hexMatch = line.match(/#[0-9a-fA-F]{3,8}\b/);
      if (hexMatch) {
        // Exclude svg viewBox/ids if false positive or allow standard token usage
        console.error(`\x1b[31m[DESIGN LINT ERROR]\x1b[0m ${filePath}:${lineNum} - Raw hex color "${hexMatch[0]}" found in src/. Use design tokens (e.g., var(--surface-solid), var(--accent)): "${line.trim()}"`);
        hasErrors = true;
      }
    }
  });
}

console.log('🔍 Running Design System Lint (Typography floor ≥ 12px & No raw hex in src/)...');
scanDirectory(SRC_DIR);

if (hasErrors) {
  console.error('\n❌ Design System Lint failed. Please fix the above issues.');
  process.exit(1);
} else {
  console.log('✅ Design System Lint passed: All font sizes ≥ 12px and 0 raw hex colors in src/.');
}
