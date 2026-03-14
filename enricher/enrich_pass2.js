#!/usr/bin/env node
/**
 * Second-pass enrichment for companies that had no results on first pass.
 *
 * Changes from first pass:
 *   1. Uses "site:linkedin.com/in {company} CEO OR founder" query (more targeted)
 *   2. Falls back to "{company} who founded" if first query fails
 *   3. Relaxed parser — grabs any LinkedIn /in/ profile associated with the company
 *   4. Uses company URL/domain in query when available for specificity
 *
 * Usage:
 *   node enrich_pass2.js              # Run second pass
 *   node enrich_pass2.js --dry-run    # Preview
 *   node enrich_pass2.js --status     # Show stats
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const FOUNDERS_FILE = path.resolve(__dirname, '../vc-main/founders.json');
const PROGRESS_FILE = path.resolve(__dirname, 'progress_pass2.json');
const ENV_FILE = path.resolve(__dirname, '.env');
const SAVE_EVERY = 10;
const DELAY_MS = 500;

function loadApiKey() {
  if (!fs.existsSync(ENV_FILE)) {
    console.error('ERROR: .env file not found.');
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
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`Parse error: ${e.message}`)); }
      });
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

// Relaxed parser — grabs LinkedIn profiles more aggressively
function parseResultsRelaxed(searchResults, companyName) {
  const founders = [];
  let ceo = null;
  const seenNames = new Set();
  const seenLinkedins = new Set();
  const companyLower = companyName.toLowerCase();
  // Use first significant word of company name for matching
  const companyWords = companyLower.split(/[\s,.\-&]+/).filter(w => w.length > 2);

  // Knowledge graph
  const kg = searchResults.knowledgeGraph;
  if (kg && kg.attributes) {
    const founderAttr = kg.attributes.Founder || kg.attributes.Founders ||
                        kg.attributes['Co-founders'] || kg.attributes['Founded by'];
    if (founderAttr) {
      const names = founderAttr.split(/,\s*|\s+and\s+/).map(n => n.trim()).filter(Boolean);
      for (const name of names) {
        if (name && !seenNames.has(name.toLowerCase())) {
          seenNames.add(name.toLowerCase());
          founders.push({ name, linkedin: '' });
        }
      }
    }
    const ceoAttr = kg.attributes.CEO || kg.attributes['Chief executive officer'] ||
                    kg.attributes['Chief Executive Officer'];
    if (ceoAttr) {
      ceo = { name: ceoAttr.trim(), linkedin: '' };
    }
  }

  const organic = searchResults.organic || [];

  // First pass: look for LinkedIn profiles with founder/CEO signals
  for (const result of organic) {
    const link = result.link || '';
    const title = result.title || '';
    const snippet = result.snippet || '';

    const linkedinMatch = link.match(/linkedin\.com\/in\/([a-zA-Z0-9_%-]+)/);
    if (!linkedinMatch) continue;

    const linkedinUrl = `https://linkedin.com/in/${linkedinMatch[1]}`;
    if (seenLinkedins.has(linkedinUrl.toLowerCase())) continue;
    seenLinkedins.add(linkedinUrl.toLowerCase());

    // Extract person name from LinkedIn title format
    let personName = '';
    const titleParts = title.split(/\s*[-–—|]\s*/);
    if (titleParts.length > 0) {
      personName = titleParts[0].trim();
    }
    if (!personName || personName.toLowerCase().includes('linkedin') || personName.length < 3) continue;

    const combined = (title + ' ' + snippet).toLowerCase();
    const isFounder = combined.includes('founder') || combined.includes('co-founder') ||
                      combined.includes('cofounder') || combined.includes('founded');
    const isCeo = combined.includes('ceo') || combined.includes('chief executive') ||
                  combined.includes('chief exec');

    // Check company relevance — does the result mention the company?
    const mentionsCompany = companyWords.some(w => combined.includes(w));

    if (mentionsCompany || isFounder || isCeo) {
      if (isFounder && !seenNames.has(personName.toLowerCase())) {
        seenNames.add(personName.toLowerCase());
        founders.push({ name: personName, linkedin: linkedinUrl });
      }
      if (isCeo && !ceo) {
        ceo = { name: personName, linkedin: linkedinUrl };
      }
    }

    // Match LinkedIn URLs to knowledge graph founders
    for (const f of founders) {
      if (!f.linkedin) {
        const firstName = f.name.split(' ')[0].toLowerCase();
        if (firstName.length > 2 && personName.toLowerCase().includes(firstName)) {
          f.linkedin = linkedinUrl;
        }
      }
    }
    if (ceo && !ceo.linkedin) {
      const firstName = ceo.name.split(' ')[0].toLowerCase();
      if (firstName.length > 2 && personName.toLowerCase().includes(firstName)) {
        ceo.linkedin = linkedinUrl;
      }
    }
  }

  // Second pass (relaxed): if we still have nothing, grab any LinkedIn profile
  // that mentions the company in its title/snippet
  if (founders.length === 0 && !ceo) {
    for (const result of organic) {
      const link = result.link || '';
      const title = result.title || '';
      const snippet = result.snippet || '';

      const linkedinMatch = link.match(/linkedin\.com\/in\/([a-zA-Z0-9_%-]+)/);
      if (!linkedinMatch) continue;

      const linkedinUrl = `https://linkedin.com/in/${linkedinMatch[1]}`;
      if (seenLinkedins.has(linkedinUrl.toLowerCase())) continue;
      seenLinkedins.add(linkedinUrl.toLowerCase());

      const titleParts = title.split(/\s*[-–—|]\s*/);
      let personName = titleParts[0] ? titleParts[0].trim() : '';
      if (!personName || personName.toLowerCase().includes('linkedin') || personName.length < 3) continue;

      const combined = (title + ' ' + snippet).toLowerCase();
      const mentionsCompany = companyWords.some(w => combined.includes(w));

      if (mentionsCompany) {
        founders.push({ name: personName, linkedin: linkedinUrl });
        if (!ceo) {
          ceo = { name: personName, linkedin: linkedinUrl };
        }
        break; // Just grab the first relevant one in relaxed mode
      }
    }
  }

  return { founders, ceo };
}

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

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

function showStatus() {
  const data = JSON.parse(fs.readFileSync(FOUNDERS_FILE, 'utf8'));
  const entries = Object.entries(data);
  const total = entries.length;
  const filled = entries.filter(([k, v]) => v.founders && v.founders.length > 0).length;
  const empty = total - filled;
  const progress = loadProgress();

  console.log(`\n  Pass 2 Status`);
  console.log(`  --------------------`);
  console.log(`  Total companies:     ${total}`);
  console.log(`  Enriched:            ${filled}`);
  console.log(`  Still empty:         ${empty}`);
  console.log(`  Pass 2 credits used: ${progress.creditsUsed}`);
  console.log(`  Pass 2 searched:     ${progress.searched.length}`);
  console.log(`  Last run:            ${progress.lastRun || 'never'}`);
  console.log();
}

async function enrich(dryRun = false) {
  const apiKey = dryRun ? 'dry-run' : loadApiKey();
  const data = JSON.parse(fs.readFileSync(FOUNDERS_FILE, 'utf8'));
  const progress = loadProgress();
  const searched = new Set(progress.searched);

  // Only target companies that are still empty
  const toEnrich = Object.entries(data).filter(([name, info]) => {
    if (info.founders && info.founders.length > 0) return false;
    if (searched.has(name)) return false;
    return true;
  });

  console.log(`\nPass 2: Found ${toEnrich.length} companies to retry.`);
  if (dryRun) {
    console.log('\n--- DRY RUN ---');
    console.log('First 20 queries:');
    toEnrich.slice(0, 20).forEach(([name, info], i) => {
      const domain = info.url ? new URL(info.url).hostname.replace('www.', '') : '';
      const query = domain
        ? `site:linkedin.com/in "${name}" OR "${domain}" CEO OR founder`
        : `site:linkedin.com/in "${name}" CEO OR founder`;
      console.log(`  ${i + 1}. ${query}`);
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

    // Build smarter query
    let domain = '';
    try {
      if (companyInfo.url) domain = new URL(companyInfo.url).hostname.replace('www.', '');
    } catch (e) {}

    // Query 1: targeted LinkedIn search
    const query1 = domain
      ? `site:linkedin.com/in "${companyName}" OR "${domain}" CEO OR founder`
      : `site:linkedin.com/in "${companyName}" CEO OR founder`;

    process.stdout.write(`[${i + 1}/${toEnrich.length}] ${companyName}... `);

    try {
      let results = await serperSearch(query1, apiKey);
      progress.creditsUsed++;
      let parsed = parseResultsRelaxed(results, companyName);

      // If first query got nothing, try a second query
      if (parsed.founders.length === 0 && !parsed.ceo) {
        const query2 = `"${companyName}" who founded CEO`;
        results = await serperSearch(query2, apiKey);
        progress.creditsUsed++;
        parsed = parseResultsRelaxed(results, companyName);
      }

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

      if ((i + 1) % SAVE_EVERY === 0) {
        fs.writeFileSync(FOUNDERS_FILE, JSON.stringify(data, null, 2));
        saveProgress(progress);
        console.log(`  [saved: ${enriched} enriched, ${progress.creditsUsed} credits used]`);
      }

      await sleep(DELAY_MS);

    } catch (err) {
      console.log(`✗ ERROR: ${err.message}`);
      errors++;
      if (err.message.includes('400') || err.message.includes('429') || err.message.includes('401') || err.message.includes('403')) {
        console.log('\nAPI limit reached or auth error. Stopping.');
        break;
      }
      if (errors > 10) {
        console.log('\nToo many errors. Stopping.');
        break;
      }
    }
  }

  fs.writeFileSync(FOUNDERS_FILE, JSON.stringify(data, null, 2));
  saveProgress(progress);

  console.log(`\n--- Pass 2 Done ---`);
  console.log(`Enriched: ${enriched}`);
  console.log(`Credits used this pass: ${progress.creditsUsed}`);
  console.log(`Total pass 2 searched: ${searched.size}`);
}

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
