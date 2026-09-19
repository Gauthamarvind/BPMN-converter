#!/usr/bin/env node
/**
 * Headless validation of BPMN 2.0 XML files using bpmn-moddle.
 * Verifies that all golden tests and BPMN test fixtures parse without
 * any syntax errors, schema violations, or import warnings.
 */

import fs from 'fs';
import path from 'path';
import { BpmnModdle } from 'bpmn-moddle';

const ROOT_DIR = process.cwd();
const moddle = new BpmnModdle();

function findBpmnFiles(dirPath) {
  if (!fs.existsSync(dirPath)) {
    return [];
  }
  return fs
    .readdirSync(dirPath)
    .filter((file) => file.endsWith('.bpmn'))
    .map((file) => path.join(dirPath, file));
}

async function validateBpmnFile(filePath) {
  const relPath = path.relative(ROOT_DIR, filePath);
  const xml = fs.readFileSync(filePath, 'utf-8');

  if (!xml || xml.trim().length === 0) {
    throw new Error(`File ${relPath} is empty`);
  }

  try {
    const { rootElement, warnings } = await moddle.fromXML(xml);

    if (!rootElement) {
      throw new Error(`Failed to parse root element in ${relPath}`);
    }

    if (warnings && warnings.length > 0) {
      const warningDetails = warnings.map((w) => w.message || JSON.stringify(w)).join('; ');
      throw new Error(`bpmn-moddle emitted warnings on ${relPath}: ${warningDetails}`);
    }

    console.log(`✓ Validated ${relPath} (Root: ${rootElement.$type})`);
  } catch (err) {
    console.error(`✗ Validation failed for ${relPath}:`, err.message || err);
    throw err;
  }
}

async function main() {
  const goldenDir = path.join(ROOT_DIR, 'backend', 'tests', 'golden');
  const fixturesDir = path.join(ROOT_DIR, 'backend', 'tests', 'fixtures');

  const goldenFiles = findBpmnFiles(goldenDir);
  const fixtureFiles = findBpmnFiles(fixturesDir);

  const allFiles = [...goldenFiles, ...fixtureFiles];

  if (allFiles.length === 0) {
    console.error('Error: No BPMN files found in backend/tests/golden/ or backend/tests/fixtures/');
    process.exit(1);
  }

  console.log(`Verifying ${allFiles.length} BPMN files with bpmn-moddle...`);

  let failureCount = 0;
  for (const file of allFiles) {
    try {
      await validateBpmnFile(file);
    } catch (err) {
      failureCount++;
    }
  }

  if (failureCount > 0) {
    console.error(`\nFailed: ${failureCount} file(s) had bpmn-moddle validation errors or warnings.`);
    process.exit(1);
  }

  console.log(`\nAll ${allFiles.length} BPMN files successfully validated with zero warnings.`);
}

main().catch((err) => {
  console.error('Unexpected error in verify_bpmn_moddle:', err);
  process.exit(1);
});
