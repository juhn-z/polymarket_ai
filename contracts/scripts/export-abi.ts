// Copies ABI from compiled artifacts into contracts/exports/abi/<Name>.json
// (just the abi, not the full artifact) so the frontend can import it
// without depending on Hardhat's artifact layout.
//
// Use:  npx hardhat run scripts/export-abi.ts

import { artifacts } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const TO_EXPORT = ["PolyVault", "MockUSDC"];

async function main() {
  const outDir = path.resolve(__dirname, "..", "exports", "abi");
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  for (const name of TO_EXPORT) {
    const art = await artifacts.readArtifact(name);
    const out = { contractName: name, abi: art.abi };
    fs.writeFileSync(path.join(outDir, `${name}.json`), JSON.stringify(out, null, 2));
    console.log(`Exported ${name} ABI → exports/abi/${name}.json`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
