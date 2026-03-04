/**
 * Cleanup verification test
 * Ensures old monolith files are removed and SPA files exist
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('Frontend cleanup', () => {
  const frontendDir = path.resolve(__dirname, '../..');

  it('should have removed index.html.bak', () => {
    const bakPath = path.join(frontendDir, 'index.html.bak');
    expect(fs.existsSync(bakPath)).toBe(false);
  });

  it('should have removed old monolith index.html', () => {
    const indexPath = path.join(frontendDir, 'index.html');
    expect(fs.existsSync(indexPath)).toBe(false);
  });

  it('should keep display.js (generated UMD bundle for Node)', () => {
    const displayJsPath = path.join(frontendDir, 'display.js');
    expect(fs.existsSync(displayJsPath)).toBe(true);
  });

  it('should have ES modules source in src/lib/display/', () => {
    const displaySrcPath = path.join(frontendDir, 'src/lib/display');
    expect(fs.existsSync(displaySrcPath)).toBe(true);
    expect(fs.existsSync(path.join(displaySrcPath, 'index.js'))).toBe(true);
    expect(fs.existsSync(path.join(displaySrcPath, 'render-html.js'))).toBe(true);
    expect(fs.existsSync(path.join(displaySrcPath, 'tokens.css'))).toBe(true);
  });

  it('should have removed old display/ CommonJS directory', () => {
    const oldDisplayDir = path.join(frontendDir, 'display');
    expect(fs.existsSync(oldDisplayDir)).toBe(false);
  });

  it('should have SPA entry point main.jsx', () => {
    const mainPath = path.join(frontendDir, 'src/main.jsx');
    expect(fs.existsSync(mainPath)).toBe(true);
  });

  it('should have removed display.js.backup', () => {
    const backupPath = path.join(frontendDir, 'display.js.backup');
    expect(fs.existsSync(backupPath)).toBe(false);
  });
});
