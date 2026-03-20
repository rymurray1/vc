#!/usr/bin/env node
/**
 * Batch Founder/CEO Enricher for 70 Companies using Serper.dev
 *
 * Returns a JSON object mapping company names to {founders: [{name: "", linkedin: ""}], ceo: {name: "", linkedin: ""}}
 *
 * Usage:
 *   node enrich_batch_70.js                  # Run enrichment and output JSON
 *   node enrich_batch_70.js --dry-run        # Preview what would be searched (no API calls)
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// --- Config ---
const ENV_FILE = path.resolve(__dirname, '.env');
const SAVE_EVERY = 10; // save progress every N companies
const DELAY_MS = 500;  // delay between API calls to be respectful

const COMPANIES = [
  'ENGIE', 'EPS Ventures', 'Emerson Collective', 'Energy Foundry', 'Energy Impact Partners',
  'Energy Innovation Capital', 'Eni', 'Extantia', 'Farvatn Ventures', 'Frankstahl',
  'Good Growth Capital', 'Grantham Foundation', 'Gravity Climate Fund', 'GS Energy', 'GS Futures',
  'GVP Climate', 'High House Investments', 'Holcim MAQER Ventures', 'Impact Science Ventures',
  'Investissement Quebec', 'KDT Ventures', 'Khosla Ventures', 'Kiko Ventures', 'Kinetics',
  'LG Tech Ventures', 'Lineage Logistics', 'Lowercarbon Capital', 'Lumens', 'Luminate NY',
  'MOL Switch', 'Marubeni', 'MassCEC', 'MassMutual', 'MassMutual Ventures',
  'Mercuria', 'Micron', 'Microsoft', 'Mistletoe', 'Mitsubishi Heavy Industry',
  'Muus Climate Partners', 'National Grid', 'Neotribe Ventures', 'Oxy Low Carbon Ventures',
  'Pear VC', 'Pentair', 'Piedmont Capital', 'Plug and Play', 'Powerhouse',
  'S2G Ventures', 'SABIC Ventures', 'Schmidt Family Foundation', 'Second Century Ventures',
  'Shell Foundation', 'Skyview Ventures', 'SOSV', 'Starlight Ventures', 'TechEnergy Ventures',
  'Tenaska', 'Trafigura', 'UCeed Investment Funds', 'UM6P Ventures', 'UP Partners',
  'United Airlines', 'Vale', 'Valo Ventures', 'VoLo Earth', 'Volta Circle', 'Voyager Ventures'
];

// --- Load API key from .env ---
function loadApiKey() {
  if (!fs.existsSync(ENV_FILE)) {
    console.error('ERROR: .env file not found at ' + ENV_FILE);
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

// --- Main enrichment loop ---
async function enrich(dryRun = false) {
  const apiKey = dryRun ? 'dry-run' : loadApiKey();
  const result = {};

  // Initialize all companies with empty results
  for (const company of COMPANIES) {
    result[company] = { founders: [], ceo: null };
  }

  console.log(`\nProcessing ${COMPANIES.length} companies...`);
  if (dryRun) {
    console.log('\n--- DRY RUN (no API calls) ---');
    console.log('First 20 companies that would be searched:');
    COMPANIES.slice(0, 20).forEach((name, i) => {
      console.log(`  ${i + 1}. "${name} founder CEO"`);
    });
    if (COMPANIES.length > 20) console.log(`  ... and ${COMPANIES.length - 20} more`);
    return;
  }

  let enriched = 0;
  let errors = 0;

  for (let i = 0; i < COMPANIES.length; i++) {
    const companyName = COMPANIES[i];
    const query = `${companyName} founder CEO`;

    process.stdout.write(`[${i + 1}/${COMPANIES.length}] ${companyName}... `);

    try {
      const results = await serperSearch(query, apiKey);

      const parsed = parseResults(results, companyName);

      if (parsed.founders.length > 0 || parsed.ceo) {
        result[companyName].founders = parsed.founders;
        result[companyName].ceo = parsed.ceo;
        enriched++;
        console.log(`✓ ${parsed.founders.length} founder(s)` + (parsed.ceo ? ` + CEO: ${parsed.ceo.name}` : ''));
      } else {
        console.log('– no results');
      }

      // Save periodically
      if ((i + 1) % SAVE_EVERY === 0) {
        console.log(`  [processed ${i + 1}/${COMPANIES.length}]`);
      }

      await sleep(DELAY_MS);

    } catch (err) {
      console.log(`✗ ERROR: ${err.message}`);
      errors++;

      // If rate limited or auth error, stop
      if (err.message.includes('429') || err.message.includes('401') || err.message.includes('403')) {
        console.log('\nAPI limit reached or auth error. Stopping.');
        break;
      }

      if (errors > 10) {
        console.log('\nToo many errors. Stopping.');
        break;
      }
    }
  }

  console.log(`\n--- Done ---`);
  console.log(`Enriched: ${enriched}/${COMPANIES.length}`);
  console.log(`\n--- Output ---\n`);
  console.log(JSON.stringify(result, null, 2));

  return result;
}

// --- CLI ---
const args = process.argv.slice(2);

if (args.includes('--dry-run')) {
  enrich(true);
} else {
  enrich(false);
}
