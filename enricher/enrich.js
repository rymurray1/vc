#!/usr/bin/env node
/**
 * Founder/CEO Enricher using Serper.dev
 *
 * Searches for founder and CEO LinkedIn data for companies in founders.json.
 * Skips already-enriched companies. Saves progress after every batch.
 *
 * Usage:
 *   node enrich.js                  # Run enrichment
 *   node enrich.js --dry-run        # Preview what would be searched (no API calls)
 *   node enrich.js --status         # Show progress stats
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// --- Config ---
const FOUNDERS_FILE = path.resolve(__dirname, '../vc-main/founders.json');
const PROGRESS_FILE = path.resolve(__dirname, 'progress.json');
const ENV_FILE = path.resolve(__dirname, '.env');
const SAVE_EVERY = 10; // save progress every N companies
const DELAY_MS = 500;  // delay between API calls to be respectful

// --- Load API key from .env ---
function loadApiKey() {
  if (!fs.existsSync(ENV_FILE)) {
    console.error('ERROR: .env file not found. Copy .env.example to .env and add your Serper API key.');
    process.exit(1);
  }
  const envContent = fs.readFileSync(ENV_FILE, 'utf8');
  const match = envContent.match(/SERPER_API_KEY=(.+)/);
  if (!match || match[1].trim() === 'your_api_key_here') {
    console.error('ERROR: Set your SERPER_API_KEY in the .env file.');
    process.exit(1);
  }
  return match[1].trim();
}

// --- Serper.dev Google Search ---
function serperSearch(query, apiKey) {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify({ q: query });
    const options = {
      hostname: 'google.serper.dev',
      path: '/search',
      method: 'POST',
      headers: {
        'X-API-KEY': apiKey,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`Serper API error ${res.statusCode}: ${data}`));
          return;
        }
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Failed to parse Serper response: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

// --- Parse search results for founder/CEO + LinkedIn ---
function parseResults(searchResults, companyName) {
  const founders = [];
  let ceo = null;
  const seenNames = new Set();
  const seenLinkedins = new Set();

  // Check knowledge graph first
  const kg = searchResults.knowledgeGraph;
  if (kg) {
    // Sometimes the knowledge graph has founder info directly
    if (kg.attributes) {
      const founderAttr = kg.attributes.Founder || kg.attributes.Founders || kg.attributes['Co-founders'];
      if (founderAttr) {
        const names = founderAttr.split(/,\s*|and\s+/).map(n => n.trim()).filter(Boolean);
        for (const name of names) {
          if (name && !seenNames.has(name.toLowerCase())) {
            seenNames.add(name.toLowerCase());
            founders.push({ name, linkedin: '' });
          }
        }
      }
      const ceoAttr = kg.attributes.CEO || kg.attributes['Chief executive officer'];
      if (ceoAttr) {
        ceo = { name: ceoAttr.trim(), linkedin: '' };
      }
    }
  }

  // Parse organic results for LinkedIn URLs and names
  const organic = searchResults.organic || [];
  for (const result of organic) {
    const link = result.link || '';
    const title = result.title || '';
    const snippet = result.snippet || '';

    // Look for LinkedIn profile URLs
    const linkedinMatch = link.match(/linkedin\.com\/in\/([a-zA-Z0-9_-]+)/);
    if (linkedinMatch) {
      const linkedinUrl = `https://linkedin.com/in/${linkedinMatch[1]}`;

      if (seenLinkedins.has(linkedinUrl.toLowerCase())) continue;
      seenLinkedins.add(linkedinUrl.toLowerCase());

      // Extract person name from title (usually "Name - Title - Company | LinkedIn")
      let personName = '';
      const titleParts = title.split(/\s*[-–—|]\s*/);
      if (titleParts.length > 0) {
        personName = titleParts[0].trim();
      }

      if (!personName || personName.toLowerCase().includes('linkedin')) continue;

      // Check if this person is a founder or CEO based on title/snippet
      const combined = (title + ' ' + snippet).toLowerCase();
      const isFounder = combined.includes('founder') || combined.includes('co-founder') || combined.includes('cofounder');
      const isCeo = combined.includes('ceo') || combined.includes('chief executive');

      if (isFounder && !seenNames.has(personName.toLowerCase())) {
        seenNames.add(personName.toLowerCase());
        founders.push({ name: personName, linkedin: linkedinUrl });
      }

      if (isCeo && !ceo) {
        ceo = { name: personName, linkedin: linkedinUrl };
      }

      // Also try to match LinkedIn URLs to founders we found from knowledge graph
      for (const f of founders) {
        if (!f.linkedin && personName.toLowerCase().includes(f.name.split(' ')[0].toLowerCase())) {
          f.linkedin = linkedinUrl;
        }
      }

      if (ceo && !ceo.linkedin && personName.toLowerCase().includes(ceo.name.split(' ')[0].toLowerCase())) {
        ceo.linkedin = linkedinUrl;
      }
    }
  }

  // If we found founders from knowledge graph but no LinkedIn results matched them,
  // do a second pass checking snippets for any mentions
  if (founders.length === 0) {
    // Fallback: look for any LinkedIn profile that mentions the company
    for (const result of organic) {
      const link = result.link || '';
      const title = result.title || '';
      const snippet = result.snippet || '';
      const combined = (title + ' ' + snippet).toLowerCase();

      const linkedinMatch = link.match(/linkedin\.com\/in\/([a-zA-Z0-9_-]+)/);
      if (linkedinMatch && combined.includes(companyName.toLowerCase().split(' ')[0])) {
        const linkedinUrl = `https://linkedin.com/in/${linkedinMatch[1]}`;
        if (seenLinkedins.has(linkedinUrl.toLowerCase())) continue;
        seenLinkedins.add(linkedinUrl.toLowerCase());

        const titleParts = title.split(/\s*[-–—|]\s*/);
        let personName = titleParts[0] ? titleParts[0].trim() : '';
        if (personName && !personName.toLowerCase().includes('linkedin')) {
          founders.push({ name: personName, linkedin: linkedinUrl });
          if (!ceo) {
            ceo = { name: personName, linkedin: linkedinUrl };
          }
        }
      }
    }
  }

  return { founders, ceo };
}

// --- Sleep helper ---
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// --- Load progress (tracks which companies have been searched) ---
function loadProgress() {
  if (fs.existsSync(PROGRESS_FILE)) {
    return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));
  }
  return { searched: [], creditsUsed: 0, lastRun: null };
}

function saveProgress(progress) {
  progress.lastRun = new Date().toISOString();
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
}

// --- Show status ---
function showStatus() {
  const data = JSON.parse(fs.readFileSync(FOUNDERS_FILE, 'utf8'));
  const entries = Object.entries(data);
  const total = entries.length;
  const filled = entries.filter(([k, v]) => v.founders && v.founders.length > 0).length;
  const empty = total - filled;

  const progress = loadProgress();

  console.log(`\n  Founders.json Status`);
  console.log(`  --------------------`);
  console.log(`  Total companies:    ${total}`);
  console.log(`  Enriched:           ${filled}`);
  console.log(`  Still empty:        ${empty}`);
  console.log(`  Serper credits used: ${progress.creditsUsed}`);
  console.log(`  Last run:           ${progress.lastRun || 'never'}`);
  console.log();
}

// --- Main enrichment loop ---
async function enrich(dryRun = false) {
  const apiKey = dryRun ? 'dry-run' : loadApiKey();
  const data = JSON.parse(fs.readFileSync(FOUNDERS_FILE, 'utf8'));
  const progress = loadProgress();
  const searched = new Set(progress.searched);

  // Find companies that need enrichment
  const toEnrich = Object.entries(data).filter(([name, info]) => {
    if (info.founders && info.founders.length > 0) return false; // already has data
    if (searched.has(name)) return false; // already searched (no results found)
    return true;
  });

  console.log(`\nFound ${toEnrich.length} companies to enrich.`);
  if (dryRun) {
    console.log('\n--- DRY RUN (no API calls) ---');
    console.log('First 20 companies that would be searched:');
    toEnrich.slice(0, 20).forEach(([name], i) => {
      console.log(`  ${i + 1}. "${name} founder CEO LinkedIn"`);
    });
    if (toEnrich.length > 20) console.log(`  ... and ${toEnrich.length - 20} more`);
    return;
  }

  if (toEnrich.length === 0) {
    console.log('Nothing to do!');
    return;
  }

  let enriched = 0;
  let errors = 0;

  const runCount = Math.min(toEnrich.length, LIMIT);
  for (let i = 0; i < runCount; i++) {
    const [companyName, companyInfo] = toEnrich[i];
    const query = `${companyName} founder CEO LinkedIn`;

    process.stdout.write(`[${i + 1}/${toEnrich.length}] ${companyName}... `);

    try {
      const results = await serperSearch(query, apiKey);
      progress.creditsUsed++;

      const parsed = parseResults(results, companyName);

      if (parsed.founders.length > 0 || parsed.ceo) {
        data[companyName].founders = parsed.founders;
        data[companyName].ceo = parsed.ceo;
        enriched++;
        console.log(`✓ ${parsed.founders.length} founder(s)` + (parsed.ceo ? ` + CEO: ${parsed.ceo.name}` : ''));
      } else {
        console.log('– no results');
      }

      searched.add(companyName);
      progress.searched = Array.from(searched);

      // Save periodically
      if ((i + 1) % SAVE_EVERY === 0) {
        fs.writeFileSync(FOUNDERS_FILE, JSON.stringify(data, null, 2));
        saveProgress(progress);
        console.log(`  [saved progress: ${enriched} enriched, ${progress.creditsUsed} credits used]`);
      }

      await sleep(DELAY_MS);

    } catch (err) {
      console.log(`✗ ERROR: ${err.message}`);
      errors++;

      // If rate limited or auth error, stop
      if (err.message.includes('429') || err.message.includes('401') || err.message.includes('403')) {
        console.log('\nAPI limit reached or auth error. Stopping.');
        console.log('Swap your API key in .env and run again to continue.');
        break;
      }

      if (errors > 10) {
        console.log('\nToo many errors. Stopping.');
        break;
      }
    }
  }

  // Final save
  fs.writeFileSync(FOUNDERS_FILE, JSON.stringify(data, null, 2));
  saveProgress(progress);

  console.log(`\n--- Done ---`);
  console.log(`Enriched: ${enriched}`);
  console.log(`Credits used this run: ${progress.creditsUsed}`);
  console.log(`Total searched: ${searched.size}`);
}

// --- CLI ---
const args = process.argv.slice(2);
const limitFlag = args.find(a => a.startsWith('--limit='));
const LIMIT = limitFlag ? parseInt(limitFlag.split('=')[1]) : Infinity;

if (args.includes('--status')) {
  showStatus();
} else if (args.includes('--dry-run')) {
  enrich(true);
} else {
  enrich(false);
}
