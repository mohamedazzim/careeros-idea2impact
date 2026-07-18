const fs = require('fs');
const path = require('path');

function walk(dir) {
  const results = [];
  try {
    for (const file of fs.readdirSync(dir)) {
      const fullPath = path.join(dir, file);
      try {
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
          results.push(...walk(fullPath));
        } else if (/\.(ts|tsx)$/.test(file)) {
          results.push(fullPath);
        }
      } catch (e) {}
    }
  } catch (e) {}
  return results;
}

const srcDir = path.join(__dirname, 'src');
const files = walk(srcDir);

const patterns = ['console.log', 'console.error', 'console.warn', 'TODO', 'FIXME', 'HACK', 'TEMP', 'PLACEHOLDER', 'MOCK', 'STUB', 'DUMMY', 'NotImplementedError'];

let found = 0;
for (const file of files) {
  const content = fs.readFileSync(file, 'utf8');
  const lines = content.split('\n');
  for (let i = 0; i < lines.length; i++) {
    for (const pattern of patterns) {
      if (lines[i].includes(pattern)) {
        const rel = path.relative(srcDir, file).replace(/\\/g, '/');
        console.log(rel + ':' + (i + 1) + ': [' + pattern + '] ' + lines[i].trim().substring(0, 150));
        found++;
        break;
      }
    }
  }
}
console.log('\nTotal issues found: ' + found);
